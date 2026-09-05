"""Bounded catalog parsing and deterministic preview; no writes or external calls."""

import csv
import hashlib
import io
import json
import zipfile
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jose import JWTError, jwt
from openpyxl import load_workbook
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.master_data import ProductInput, ProductOut

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 500
COLUMNS = list(ProductInput.model_fields)
HEADER_ALIASES = {"article_number": "sku", "product_name": "description", "product_description": "description"}


class ImportProblem(ValueError):
    pass


def read_rows(filename, content):
    if len(content) > MAX_BYTES:
        raise ImportProblem("File exceeds 2 MB.")
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        try:
            rows = csv.reader(io.StringIO(content.decode("utf-8-sig")), strict=True)
            return bounded_rows(rows)
        except (UnicodeError, csv.Error) as exc:
            raise ImportProblem("Use a UTF-8, comma-separated CSV file.") from exc
    if suffix != ".xlsx":
        raise ImportProblem("Upload a .csv or .xlsx file. Save older .xls files as .xlsx first.")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            if len(archive.infolist()) > 200 or sum(i.file_size for i in archive.infolist()) > 10 * 1024 * 1024:
                raise ImportProblem("Expanded workbook exceeds the import limit.")
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=False, keep_links=False)
        try:
            if len(workbook.worksheets) != 1:
                raise ImportProblem("Use a workbook with exactly one worksheet.")
            sheet = workbook.worksheets[0]
            if sheet.max_column and sheet.max_column > len(COLUMNS):
                raise ImportProblem("Too many worksheet columns. Use the blank template headers.")
            sheet.reset_dimensions()

            def cells():
                for row in sheet.iter_rows(max_col=len(COLUMNS) + 1):
                    if any(cell.data_type in {"f", "e"} for cell in row):
                        raise ImportProblem("Excel formulas and error cells are not supported; paste values first.")
                    yield [cell.value for cell in row]

            return bounded_rows(cells())
        finally:
            workbook.close()
    except ImportProblem:
        raise
    except Exception as exc:
        raise ImportProblem("The Excel workbook could not be read. Save it as a plain .xlsx file.") from exc


def bounded_rows(rows):
    result = []
    for index, row in enumerate(rows):
        if index > MAX_ROWS:
            if any(value not in (None, "") for value in row):
                raise ImportProblem(f"Use at most {MAX_ROWS} data rows per file.")
            # CSV is bounded by bytes; reject additional blank rows too.
            raise ImportProblem(f"Use at most {MAX_ROWS} data rows per file, without trailing blank rows.")
        while row and row[-1] in (None, ""):
            row = row[:-1]
        if len(row) > len(COLUMNS) or any(len(str(value)) > 5000 for value in row):
            raise ImportProblem("Too many columns or a cell exceeds 5,000 characters.")
        result.append(row)
    if not result or not result[0]:
        raise ImportProblem("The first row must contain column headers.")
    headers = [HEADER_ALIASES.get(str(h).strip().lower().replace(" ", "_"),
                                str(h).strip().lower().replace(" ", "_")) for h in result[0]]
    if len(set(headers)) != len(headers) or "sku" not in headers:
        raise ImportProblem("Headers must be unique and include sku.")
    unknown = set(headers) - set(COLUMNS)
    if unknown:
        raise ImportProblem("Unknown columns: " + ", ".join(sorted(unknown)))
    parsed = []
    for number, row in enumerate(result[1:], 2):
        if not row:
            continue
        if len(row) > len(headers):
            raise ImportProblem(f"Row {number} has more values than headers.")
        parsed.append((number, dict(zip(headers, row, strict=False))))
    if not parsed:
        raise ImportProblem("The file contains headers but no product rows.")
    return parsed


def product_values(product):
    return ProductOut.model_validate(product).model_dump(mode="json", exclude={"id", "client_id"})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def catalog_digest(products):
    return digest(sorted([{"id": p.id, **product_values(p)} for p in products], key=lambda p: p["id"]))


def preview_rows(filename, content, products):
    existing = {p.sku: p for p in products}
    rows = []
    sku_rows = defaultdict(list)
    for number, raw in read_rows(filename, content):
        sku = raw.get("sku")
        sku = sku.strip() if isinstance(sku, str) else sku
        old = existing.get(sku) if isinstance(sku, str) else None
        before = product_values(old) if old else None
        row = {"row": number, "sku": str(sku or ""), "action": "update" if old else "create",
               "errors": [], "warnings": [], "before": before, "after": None}
        rows.append(row)
        if not isinstance(sku, str) or not sku:
            row["errors"].append("SKU must be non-empty text. In Excel, format identifiers as Text to preserve leading zeros.")
            continue
        sku_rows[sku].append(row)
        values = dict(before or {})
        values.update({key: value.strip() if isinstance(value, str) else value
                       for key, value in raw.items() if value is not None and str(value).strip()})
        if "aliases" in raw and str(raw["aliases"] or "").strip():
            if not isinstance(raw["aliases"], str):
                row["errors"].append("Aliases must be text, separated by |.")
                continue
            values["aliases"] = [alias.strip() for alias in raw["aliases"].split("|")]
        try:
            data = ProductInput.model_validate(values)
            row["after"] = data.model_dump(mode="json")
            if row["after"] == before:
                row["action"] = "unchanged"
            if data.on_hand is None:
                row["warnings"].append("Stock remains unknown.")
            elif datetime.now(UTC) - data.stock_updated_at > timedelta(hours=24):
                row["warnings"].append("Stock snapshot is older than 24 hours and requires order review.")
        except ValidationError as exc:
            row["errors"].extend(f"{'.'.join(map(str, e['loc'])) or 'Row'}: {e['msg']}" for e in exc.errors())
    for repeated in sku_rows.values():
        if len(repeated) > 1:
            for row in repeated:
                row["errors"].append("Duplicate SKU in this file.")
    # Check identifiers against the final catalog, including all rows in this upload.
    final = {p.sku: product_values(p) for p in products}
    final.update({r["sku"]: r["after"] for r in rows if r["after"] and not r["errors"]})
    identifiers = defaultdict(set)
    for sku, values in final.items():
        for identifier in [sku, *values["aliases"]]:
            identifiers[identifier].add(sku)
    for row in rows:
        if row["after"]:
            for identifier in [row["sku"], *row["after"]["aliases"]]:
                if len(identifiers[identifier]) > 1:
                    row["errors"].append(f"SKU or alias '{identifier}' belongs to another product.")
    return rows


def preview_token(client_id, user_id, content, products):
    return jwt.encode({"kind": "catalog_import", "client": client_id, "actor": user_id,
                       "file": hashlib.sha256(content).hexdigest(), "catalog": catalog_digest(products),
                       "exp": datetime.now(UTC) + timedelta(minutes=15)}, settings.secret_key, algorithm="HS256")


def verify_preview(token, client_id, user_id, content, products):
    try:
        claims = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        expected = {"kind": "catalog_import", "client": client_id, "actor": user_id,
                    "file": hashlib.sha256(content).hexdigest(), "catalog": catalog_digest(products)}
        if any(claims.get(key) != value for key, value in expected.items()):
            raise ImportProblem("The file or catalog changed. Preview again before confirming.")
    except JWTError as exc:
        raise ImportProblem("The preview expired or is invalid. Preview the file again.") from exc

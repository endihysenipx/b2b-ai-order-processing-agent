from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.services.email.lutz_parser import LutzOrder, LutzOrderItem

if TYPE_CHECKING:
    from app.services.aws_document_processing.service import TextractTable, TextractTableCell


class LesninaMappedItem(BaseModel):
    model_number: str
    article_number: str
    quantity: int = Field(gt=0)
    position: str
    source_page: int | None = None
    source_row: int
    confidence: float | None = None
    requires_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)

    def to_order_item(self) -> LutzOrderItem:
        return LutzOrderItem(
            model_number=self.model_number,
            article_number=self.article_number,
            quantity=self.quantity,
            position=self.position,
        )


class LesninaTableMapping(BaseModel):
    items: list[LesninaMappedItem] = Field(default_factory=list)
    requires_review: bool = False
    issues: list[str] = Field(default_factory=list)


class LesninaOrderMapping(BaseModel):
    order: LutzOrder
    item_details: list[LesninaMappedItem] = Field(default_factory=list)
    requires_review: bool = False
    issues: list[str] = Field(default_factory=list)


class LesninaEmailMapping(BaseModel):
    orders: list[LesninaOrderMapping] = Field(default_factory=list)
    requires_review: bool = False
    issues: list[str] = Field(default_factory=list)


class LesninaTableMapper:
    _item_code_pattern = re.compile(r"^(?P<model>[A-Z0-9]+(?:-[A-Z0-9]+)*)-(?P<article>[A-Z0-9]+)$")
    _position_headers = {"pos", "poz", "position"}
    _article_headers = {"artnr", "artikelnummer", "brart", "sifraartikla"}
    _quantity_headers = {"menge", "qty", "quantity", "koli", "kolicin", "kolicina", "kolleri"}

    def __init__(self, review_confidence_threshold: float = 90.0) -> None:
        self.review_confidence_threshold = review_confidence_threshold

    def map_tables(self, tables: list[TextractTable]) -> LesninaTableMapping:
        items: list[LesninaMappedItem] = []
        issues: list[str] = []
        missing_quantity_issues: list[tuple[str, str]] = []
        recognized_tables = 0

        for table in tables:
            rows = self._rows(table)
            header = self._find_header(rows)
            if header is None:
                continue
            recognized_tables += 1
            header_row, position_column, article_column, quantity_column = header
            used_quantity_cells: set[tuple[int, int]] = set()
            for row_number, row in sorted(rows.items()):
                if row_number <= header_row:
                    continue
                code_cell = row.get(article_column)
                if code_cell is None or not code_cell.text.strip():
                    continue
                code = re.sub(r"\s+", "", code_cell.text).upper()
                code_match = self._item_code_pattern.fullmatch(code)
                if code_match is None:
                    if "-" in code:
                        issues.append(f"Page {table.page or '?'} row {row_number}: unrecognized item code '{code_cell.text}'.")
                    continue

                quantity_cell = row.get(quantity_column)
                quantity = self._parse_quantity(quantity_cell.text if quantity_cell else "")
                quantity_key = (quantity_cell.row, quantity_column) if quantity_cell else None
                if quantity_key in used_quantity_cells:
                    quantity_cell = None
                    quantity = None
                    quantity_key = None
                if quantity is None:
                    quantity_cell, quantity = self._find_continuation_quantity(
                        rows,
                        row_number,
                        article_column,
                        quantity_column,
                        used_quantity_cells,
                    )
                    quantity_key = (quantity_cell.row, quantity_column) if quantity_cell else None
                if quantity is None:
                    missing_quantity_issues.append(
                        (code, f"Page {table.page or '?'} row {row_number}: invalid or missing quantity for '{code}'.")
                    )
                    continue
                if quantity_key is not None:
                    used_quantity_cells.add(quantity_key)

                position_cell = row.get(position_column) if position_column is not None else None
                raw_position = position_cell.text.strip() if position_cell and position_cell.text.strip() else ""
                position = self._normalize_position(raw_position) or ""
                confidence_values = [
                    value
                    for value in (code_cell.confidence, quantity_cell.confidence if quantity_cell else None)
                    if value is not None
                ]
                confidence = min(confidence_values) if confidence_values else None
                review_reasons: list[str] = []
                if confidence is None:
                    review_reasons.append("Textract did not provide confidence for the code and quantity.")
                elif confidence < self.review_confidence_threshold:
                    review_reasons.append(
                        f"Confidence {confidence:.1f}% is below the {self.review_confidence_threshold:.1f}% review threshold."
                    )

                items.append(
                    LesninaMappedItem(
                        model_number=code_match.group("model"),
                        article_number=code_match.group("article"),
                        quantity=quantity,
                        position=position,
                        source_page=table.page,
                        source_row=row_number,
                        confidence=confidence,
                        requires_review=bool(review_reasons),
                        review_reasons=review_reasons,
                    )
                )

        deduplicated_items: dict[tuple[str, str, int, str], LesninaMappedItem] = {}
        for item in items:
            if not item.position:
                matching_positions = {
                    existing.position
                    for existing in deduplicated_items.values()
                    if existing.model_number == item.model_number
                    and existing.article_number == item.article_number
                    and existing.quantity == item.quantity
                }
                if len(matching_positions) == 1:
                    item.position = matching_positions.pop()
                else:
                    item.position = str(item.source_row)
                    item.requires_review = True
                    item.review_reasons.append("Textract did not read a usable item position.")
            key = (item.model_number, item.article_number, item.quantity, item.position)
            existing = deduplicated_items.get(key)
            existing_confidence = existing.confidence if existing and existing.confidence is not None else -1
            item_confidence = item.confidence if item.confidence is not None else -1
            if existing is None or item_confidence > existing_confidence:
                deduplicated_items[key] = item
        items = list(deduplicated_items.values())
        mapped_codes = {f"{item.model_number}-{item.article_number}" for item in items}
        issues.extend(message for code, message in missing_quantity_issues if code not in mapped_codes)

        if recognized_tables == 0:
            issues.append("No Lesnina item table with article and quantity columns was found.")
        elif not items:
            issues.append("A Lesnina item table was found, but no valid item rows could be mapped.")

        return LesninaTableMapping(
            items=items,
            requires_review=bool(issues) or any(item.requires_review for item in items),
            issues=list(dict.fromkeys(issues)),
        )

    def _find_continuation_quantity(
        self,
        rows: dict[int, dict[int, TextractTableCell]],
        item_row: int,
        article_column: int,
        quantity_column: int,
        used_quantity_cells: set[tuple[int, int]],
    ) -> tuple[TextractTableCell | None, int | None]:
        for row_number, row in sorted(rows.items()):
            if row_number <= item_row:
                continue
            candidate = row.get(quantity_column)
            if candidate is not None and (candidate.row, quantity_column) in used_quantity_cells:
                continue
            quantity = self._parse_quantity(candidate.text if candidate else "")
            if quantity is not None:
                return candidate, quantity
        return None, None

    @staticmethod
    def merge_order(order: LutzOrder, mapping: LesninaTableMapping) -> LesninaOrderMapping:
        merged_order = order.model_copy(update={"items": [item.to_order_item() for item in mapping.items]})
        issues = list(mapping.issues)
        for field_name, label in (
            ("delivery_address", "delivery address"),
            ("preferred_delivery_week", "preferred delivery week"),
            ("commission_name", "commission name"),
        ):
            if not getattr(merged_order, field_name):
                issues.append(f"The email is missing the {label}.")
        return LesninaOrderMapping(
            order=merged_order,
            item_details=mapping.items,
            requires_review=bool(issues) or mapping.requires_review,
            issues=issues,
        )

    @classmethod
    def merge_email_orders(cls, orders: list[LutzOrder], mapping: LesninaTableMapping) -> LesninaEmailMapping:
        if len(orders) == 1:
            merged = cls.merge_order(orders[0], mapping)
            return LesninaEmailMapping(
                orders=[merged],
                requires_review=merged.requires_review,
                issues=list(merged.issues),
            )

        merged_orders: list[LesninaOrderMapping] = []
        email_issues: list[str] = []
        for index, order in enumerate(orders, start=1):
            prefix = str(index)
            order_items = [
                item for item in mapping.items if item.position == prefix or item.position.startswith(f"{prefix}.")
            ]
            order_mapping = LesninaTableMapping(
                items=order_items,
                requires_review=any(item.requires_review for item in order_items),
                issues=[] if order_items else [f"No scanned items were matched to commission {order.commission_number}."],
            )
            merged = cls.merge_order(order, order_mapping)
            merged_orders.append(merged)
            email_issues.extend(merged.issues)
        return LesninaEmailMapping(
            orders=merged_orders,
            requires_review=any(order.requires_review for order in merged_orders),
            issues=list(dict.fromkeys(email_issues)),
        )

    @classmethod
    def _find_header(
        cls, rows: dict[int, dict[int, TextractTableCell]]
    ) -> tuple[int, int | None, int, int] | None:
        for row_number, row in sorted(rows.items()):
            normalized = {column: cls._normalize_header(cell.text) for column, cell in row.items()}
            article_column = next(
                (column for column, value in normalized.items() if cls._matches_header(value, cls._article_headers)),
                None,
            )
            quantity_column = next(
                (column for column, value in normalized.items() if cls._matches_header(value, cls._quantity_headers)),
                None,
            )
            if quantity_column is None:
                price_column = next(
                    (column for column, value in normalized.items() if "komad" in value or "cena" in value),
                    None,
                )
                previous_column = price_column - 1 if price_column is not None else 0
                if previous_column > 0 and cls._column_has_quantities(rows, row_number, previous_column):
                    quantity_column = previous_column
            if article_column is None or quantity_column is None:
                continue
            # Textract frequently merges the Croatian/Serbian quantity, unit-price,
            # and total-price headings into the price column. The row values remain
            # in the immediately preceding column, so prefer it when it contains
            # valid integer quantities.
            quantity_header = normalized[quantity_column]
            previous_column = quantity_column - 1
            if (
                any(marker in quantity_header for marker in ("cijena", "cjena", "cena", "jed"))
                and previous_column > 0
                and cls._column_has_quantities(rows, row_number, previous_column)
            ):
                quantity_column = previous_column
            position_column = next(
                (column for column, value in normalized.items() if cls._matches_header(value, cls._position_headers)),
                None,
            )
            return row_number, position_column, article_column, quantity_column
        return None

    @classmethod
    def _column_has_quantities(
        cls, rows: dict[int, dict[int, TextractTableCell]], header_row: int, column: int
    ) -> bool:
        return any(
            cls._parse_quantity(cell.text) is not None
            for row_number, row in rows.items()
            if row_number > header_row
            for cell in [row.get(column)]
            if cell is not None
        )

    @staticmethod
    def _rows(table: TextractTable) -> dict[int, dict[int, TextractTableCell]]:
        rows: dict[int, dict[int, TextractTableCell]] = {}
        for cell in table.cells:
            rows.setdefault(cell.row, {})[cell.column] = cell
        return rows

    @staticmethod
    def _normalize_header(value: str) -> str:
        folded = value.casefold().replace("č", "c").replace("ć", "c").replace("š", "s").replace("ž", "z")
        return re.sub(r"[^a-z0-9]", "", folded)

    @staticmethod
    def _matches_header(value: str, candidates: set[str]) -> bool:
        return any(value.startswith(candidate) for candidate in candidates)

    @staticmethod
    def _parse_quantity(value: str) -> int | None:
        if value.strip().upper() in {"I", "L", "|"}:
            return 1
        match = re.match(r"^\s*(\d+(?:[.,]\d+)?)", value)
        if match is None:
            return None
        try:
            quantity = Decimal(match.group(1).replace(",", "."))
        except InvalidOperation:
            return None
        if quantity <= 0 or quantity != quantity.to_integral_value():
            return None
        return int(quantity)

    @staticmethod
    def _normalize_position(value: str) -> str | None:
        position = value.strip().upper()
        if position in {"I", "L", "|"}:
            return "1"
        position = position.replace(",", ".")
        return position if re.fullmatch(r"\d+(?:\.\d+)*", position) else None

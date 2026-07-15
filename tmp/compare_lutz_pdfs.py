from __future__ import annotations

import json
import re
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
AUDIT = json.loads((ROOT / "tmp/corpus-audit/audit.json").read_text(encoding="utf-8"))


def compact(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


failures: list[str] = []
checked = 0
for record in AUDIT["records"]:
    pdfs = [Path(a["path"]) for a in record["attachments"] if a["name"].lower().endswith(".pdf")]
    if not pdfs:
        continue
    items = [item for order in record["preview"]["orders"] for item in order["items"]]
    checked += len(pdfs)
    text = "\n".join(
        page.extract_text() or "" for pdf in pdfs for page in PdfReader(pdf).pages
    )
    haystack = compact(text)
    missing: list[str] = []
    for item in items:
        model = compact(item.get("model_number") or "")
        article = compact(item.get("article_number") or "")
        if model and article and model + article not in haystack:
            missing.append(f"{item.get('position')}: {model}-{article} x{item['quantity']}")
        elif article and article not in haystack:
            missing.append(f"{item.get('position')}: [missing model]-{article} x{item['quantity']}")
    if missing:
        failures.append(f"{record['index']:03d} {record['filename']}: {', '.join(missing)}")
    print(
        f"{record['index']:03d} {record['preview']['orders'][0]['commission_number']}: "
        f"{len(items) - len(missing)}/{len(items)} item codes found across {len(pdfs)} PDF(s)"
    )

print(f"PDFS_CHECKED={checked}")
print(f"PDF_CODE_FAILURES={len(failures)}")
for failure in failures:
    print("MISSING", failure)

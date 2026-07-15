from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.aws_document_processing import LesninaTableMapper  # noqa: E402
from app.services.aws_document_processing.service import TextractTable  # noqa: E402
from app.services.email.lutz_parser import LutzOrder  # noqa: E402


path = ROOT / "tmp" / "corpus-audit" / "lesnina-textract.json"
data = json.loads(path.read_text(encoding="utf-8"))
mapper = LesninaTableMapper()
for record in data:
    mapping = mapper.map_tables([TextractTable.model_validate(table) for table in record.get("tables", [])])
    record["mapping"] = mapping.model_dump(mode="json")
    if len(record.get("email_orders", [])) == 1:
        record["merged"] = mapper.merge_order(
            LutzOrder.model_validate(record["email_orders"][0]), mapping
        ).model_dump(mode="json")
path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

for record in data:
    mapping = record["mapping"]
    print(
        record["email"],
        "|",
        [(item["model_number"], item["article_number"], item["quantity"], item["position"]) for item in mapping["items"]],
        "| review=",
        mapping["requires_review"],
        "| issues=",
        mapping["issues"],
    )

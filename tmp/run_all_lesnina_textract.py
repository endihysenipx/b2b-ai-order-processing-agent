from __future__ import annotations

import json
import sys
import time
from email import policy
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.services.aws_document_processing import AwsDocumentProcessingService, LesninaTableMapper  # noqa: E402
from app.services.email.intake import parse_email_intake  # noqa: E402


OUT = ROOT / "tmp" / "corpus-audit" / "lesnina-textract.json"
service = AwsDocumentProcessingService(settings)
jobs = []

for email_path in sorted((ROOT / "Lesnina").glob("*.eml")):
    raw = email_path.read_bytes()
    preview = parse_email_intake(raw)
    if preview.message_type != "order" or not preview.ocr_attachment_names:
        continue
    message = BytesParser(policy=policy.default).parsebytes(raw)
    attachment = next(
        part for part in message.iter_attachments() if (part.get_filename() or "").casefold().endswith((".tif", ".tiff"))
    )
    content = attachment.get_payload(decode=True) or b""
    with Image.open(BytesIO(content)) as image:
        page_count = image.n_frames
    started = service.start_table_analysis(attachment.get_filename() or "document.tiff", content)
    jobs.append(
        {
            "email": email_path.name,
            "attachment": attachment.get_filename(),
            "pages": page_count,
            "preview": preview,
            "job_id": started.job_id,
        }
    )
    print(f"STARTED {len(jobs):02d}/25 | {email_path.name} | pages={page_count}", flush=True)

pending = {job["job_id"] for job in jobs}
results = {}
for _ in range(120):
    for job in jobs:
        if job["job_id"] not in pending:
            continue
        result = service.get_table_analysis(job["job_id"])
        if result.status != "IN_PROGRESS":
            results[job["job_id"]] = result
            pending.remove(job["job_id"])
            print(f"FINISHED | {job['email']} | {result.status}", flush=True)
    if not pending:
        break
    time.sleep(3)

report = []
for job in jobs:
    result = results.get(job["job_id"])
    preview = job["preview"]
    entry = {
        "email": job["email"],
        "attachment": job["attachment"],
        "pages": job["pages"],
        "job_id": job["job_id"],
        "status": result.status if result else "TIMEOUT",
        "email_orders": [order.model_dump(mode="json") for order in preview.orders],
    }
    if result:
        entry["textract_pages"] = result.pages
        entry["tables"] = [table.model_dump(mode="json") for table in result.tables]
        entry["lines"] = [line.model_dump(mode="json") for line in result.lines]
        entry["mapping"] = result.lesnina_mapping.model_dump(mode="json") if result.lesnina_mapping else None
        if result.lesnina_mapping and len(preview.orders) == 1:
            entry["merged"] = LesninaTableMapper.merge_order(
                preview.orders[0], result.lesnina_mapping
            ).model_dump(mode="json")
    report.append(entry)

OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"REPORT={OUT}")
print(f"JOBS={len(jobs)} PAGES={sum(job['pages'] for job in jobs)} PENDING={len(pending)}")
if pending:
    raise SystemExit(f"Timed out waiting for {len(pending)} Textract jobs")

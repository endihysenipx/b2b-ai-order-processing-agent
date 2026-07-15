import json
import sys
import time
from email import policy
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path

from PIL import Image

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "backend"))

from app.core.config import settings
from app.services.aws_document_processing import AwsDocumentProcessingService, LesninaTableMapper
from app.services.email.intake import parse_email_intake

EMAIL_NAMES = [
    "#1028460 Bestellung KVZBL2 von Lutz (3!2026070732116).eml",
    "#1024679 Bestellung KJPAZ9 von Lutz (3!2026062621946).eml",
    "#1028408 Bestellung KNCADJ von Lutz (3!2026070731851).eml",
    "#1025877 Bestellung HVSTW5 von Lutz (3!2026063032200).eml",
]

service = AwsDocumentProcessingService(settings)
jobs = []

for email_name in EMAIL_NAMES:
    email_path = root / "Lesnina" / email_name
    email_bytes = email_path.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(email_bytes)
    attachment = next(
        part for part in message.walk() if (part.get_filename() or "").casefold().endswith((".tif", ".tiff"))
    )
    attachment_bytes = attachment.get_payload(decode=True)
    page_count = Image.open(BytesIO(attachment_bytes)).n_frames
    preview = parse_email_intake(email_bytes)
    started = service.start_table_analysis(attachment.get_filename() or "document.tiff", attachment_bytes)
    jobs.append(
        {
            "email_name": email_name,
            "attachment_name": attachment.get_filename(),
            "page_count": page_count,
            "preview": preview,
            "job_id": started.job_id,
        }
    )
    print(f"STARTED | {email_name} | {page_count} pages | {started.job_id}")

pending = {job["job_id"] for job in jobs}
results = {}
for _ in range(30):
    for job in jobs:
        job_id = job["job_id"]
        if job_id not in pending:
            continue
        result = service.get_table_analysis(job_id)
        if result.status != "IN_PROGRESS":
            results[job_id] = result
            pending.remove(job_id)
            print(f"FINISHED | {job['email_name']} | {result.status}")
    if not pending:
        break
    time.sleep(2)

report = []
for job in jobs:
    result = results.get(job["job_id"])
    preview = job["preview"]
    entry = {
        "email_name": job["email_name"],
        "attachment_name": job["attachment_name"],
        "page_count": job["page_count"],
        "job_id": job["job_id"],
        "status": result.status if result else "TIMEOUT",
        "email_preview": preview.model_dump(mode="json"),
    }
    if result and result.lesnina_mapping:
        entry["table_count"] = len(result.tables)
        entry["line_count"] = len(result.lines)
        entry["mapping"] = result.lesnina_mapping.model_dump(mode="json")
        if len(preview.orders) == 1:
            entry["merged_order"] = LesninaTableMapper.merge_order(
                preview.orders[0], result.lesnina_mapping
            ).model_dump(mode="json")
    report.append(entry)

output = Path(__file__).with_name("results.json")
output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"REPORT | {output}")
if pending:
    raise SystemExit(f"Timed out waiting for {len(pending)} Textract jobs")

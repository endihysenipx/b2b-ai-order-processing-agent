from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from email import policy
from email.parser import BytesParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.email.intake import parse_email_intake  # noqa: E402


SOURCE_DIRS = [ROOT / "Email Samples", ROOT / "Lesnina"]
OUT = ROOT / "tmp" / "corpus-audit"
ATTACHMENTS = OUT / "attachments"
ATTACHMENTS.mkdir(parents=True, exist_ok=True)


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return value[:100] or "attachment"


def body_text(message) -> str:
    body = message.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    return str(body.get_content()).replace("\r", "")


records = []
paths = sorted({path for source in SOURCE_DIRS for path in source.rglob("*.eml")})
for email_index, path in enumerate(paths, start=1):
    raw = path.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(raw)
    body = body_text(message)
    preview = parse_email_intake(raw)
    attachments = []
    for attachment_index, part in enumerate(message.iter_attachments(), start=1):
        original_name = part.get_filename() or f"attachment-{attachment_index}"
        payload = part.get_payload(decode=True) or b""
        digest = hashlib.sha256(payload).hexdigest()
        output_name = f"{email_index:03d}_{attachment_index:02d}_{safe_name(original_name)}"
        output_path = ATTACHMENTS / output_name
        output_path.write_bytes(payload)
        attachments.append(
            {
                "name": original_name,
                "content_type": part.get_content_type(),
                "size": len(payload),
                "sha256": digest,
                "path": str(output_path),
            }
        )

    records.append(
        {
            "index": email_index,
            "path": str(path),
            "folder": str(path.parent.relative_to(ROOT)),
            "filename": path.name,
            "subject": str(message.get("Subject", "")),
            "from": str(message.get("From", "")),
            "body": body,
            "attachments": attachments,
            "preview": preview.model_dump(mode="json"),
        }
    )

summary = {
    "emails": len(records),
    "folders": dict(Counter(record["folder"] for record in records)),
    "message_types": dict(Counter(record["preview"]["message_type"] for record in records)),
    "next_actions": dict(Counter(record["preview"]["next_action"] for record in records)),
    "profiles": dict(Counter(str(record["preview"]["client_profile"]) for record in records)),
    "attachments": dict(
        Counter(Path(item["name"]).suffix.casefold() or "<none>" for record in records for item in record["attachments"])
    ),
    "order_emails": sum(record["preview"]["message_type"] == "order" for record in records),
    "order_blocks": sum(len(record["preview"]["orders"]) for record in records),
    "items": sum(len(order["items"]) for record in records for order in record["preview"]["orders"]),
}
(OUT / "audit.json").write_text(
    json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print(f"OUTPUT={OUT / 'audit.json'}")

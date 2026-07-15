import json
import sys
from collections import Counter
from email import policy
from email.parser import BytesParser
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))

from app.services.email.intake import parse_email_intake
from app.services.email.lutz_parser import LutzEmailParseError, parse_lutz_email

folder = root / "Email Samples" / "NEW LUTZ SAMPLES"
records = []

for path in sorted(folder.glob("*.eml")):
    raw = path.read_bytes()
    message = BytesParser(policy=policy.default).parsebytes(raw)
    attachments = []
    for part in message.iter_attachments():
        filename = part.get_filename() or "unnamed-attachment"
        attachments.append(
            {
                "filename": filename,
                "content_type": part.get_content_type(),
                "size": len(part.get_payload(decode=True) or b""),
            }
        )
    intake_error = None
    try:
        intake = parse_email_intake(raw)
    except Exception as exc:
        intake = None
        intake_error = f"{type(exc).__name__}: {exc}"
    parser_error = None
    try:
        parsed = parse_lutz_email(raw)
    except LutzEmailParseError as exc:
        parsed = None
        parser_error = str(exc)

    orders = parsed.orders if parsed else []
    records.append(
        {
            "filename": path.name,
            "subject": str(message.get("Subject", "")),
            "sender": str(message.get("From", "")),
            "attachments": attachments,
            "detected_profile": intake.client_profile if intake else None,
            "detection_confidence": intake.client_detection.confidence if intake else None,
            "detection_evidence": intake.client_detection.evidence if intake else [],
            "message_type": intake.message_type if intake else None,
            "next_action": intake.next_action if intake else None,
            "intake_error": intake_error,
            "parser_success": parsed is not None,
            "parser_error": parser_error,
            "orders": [order.model_dump(mode="json") for order in orders],
        }
    )

summary = {
    "email_count": len(records),
    "subject_order_count": sum("bestellung" in record["subject"].casefold() for record in records),
    "message_types": Counter(str(record["message_type"]) for record in records),
    "detected_profiles": Counter(str(record["detected_profile"]) for record in records),
    "next_actions": Counter(str(record["next_action"]) for record in records),
    "attachment_extensions": Counter(
        Path(attachment["filename"]).suffix.casefold() or "<none>"
        for record in records
        for attachment in record["attachments"]
    ),
    "parser_success_count": sum(record["parser_success"] for record in records),
    "parsed_order_blocks": sum(len(record["orders"]) for record in records),
    "parsed_items": sum(len(order["items"]) for record in records for order in record["orders"]),
    "orders_missing_store": sum(not order["store_address"] for record in records for order in record["orders"]),
    "orders_missing_delivery": sum(not order["delivery_address"] for record in records for order in record["orders"]),
    "orders_missing_week": sum(not order["preferred_delivery_week"] for record in records for order in record["orders"]),
    "orders_missing_name": sum(not order["commission_name"] for record in records for order in record["orders"]),
    "orders_without_items": sum(not order["items"] for record in records for order in record["orders"]),
}

output = root / "tmp" / "new_lutz_analysis.json"
output.write_text(
    json.dumps({"summary": summary, "records": records}, ensure_ascii=False, indent=2, default=dict),
    encoding="utf-8",
)
print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))
print(f"REPORT={output}")

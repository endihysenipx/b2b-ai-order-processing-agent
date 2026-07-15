import json
from pathlib import Path

report = json.loads(Path(__file__).with_name("new_lutz_analysis.json").read_text(encoding="utf-8"))
for record in report["records"]:
    items = sum(len(order["items"]) for order in record["orders"])
    commissions = ",".join(order["commission_number"] for order in record["orders"]) or "-"
    attachment_names = ",".join(item["filename"] for item in record["attachments"]) or "-"
    print(
        f"{record['message_type']:22} | profile={str(record['detected_profile']):6} | "
        f"parser={str(record['parser_success']):5} | blocks={len(record['orders']):2} | items={items:2} | "
        f"komm={commissions:20} | att={attachment_names} | {record['filename']}"
    )

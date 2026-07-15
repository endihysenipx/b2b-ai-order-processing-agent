from __future__ import annotations

import json
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
OUT = ROOT / "tmp" / "corpus-audit" / "live-final-audit.json"

token = httpx.post(
    f"{BASE}/api/v1/auth/login",
    json={"email": "admin@example.com", "password": "Admin123!"},
    timeout=20,
).raise_for_status().json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

email_paths = sorted([*(ROOT / "Email Samples").rglob("*.eml"), *(ROOT / "Lesnina").glob("*.eml")])
email_results = []
failures = []
for index, path in enumerate(email_paths, start=1):
    with path.open("rb") as source:
        response = httpx.post(
            f"{BASE}/api/v1/emails/preview",
            headers=headers,
            files={"file": (path.name, source, "message/rfc822")},
            timeout=30,
        )
    if response.status_code != 200:
        failures.append(f"{path.name}: preview HTTP {response.status_code}: {response.text}")
        continue
    preview = response.json()
    if preview["message_type"] == "order":
        for order in preview["orders"]:
            for field in ("store_address", "delivery_address", "preferred_delivery_week", "commission_number"):
                if not order.get(field):
                    failures.append(f"{path.name} / {order['commission_number']}: missing {field}")
        if not preview["ocr_attachment_names"] and any(not order["items"] for order in preview["orders"]):
            failures.append(f"{path.name}: non-OCR order has no items")
    email_results.append(
        {
            "index": index,
            "email": path.name,
            "message_type": preview["message_type"],
            "action": preview["next_action"],
            "orders": len(preview["orders"]),
            "items": sum(len(order["items"]) for order in preview["orders"]),
        }
    )

saved_textract = json.loads((ROOT / "tmp" / "corpus-audit" / "lesnina-textract.json").read_text(encoding="utf-8"))
textract_results = []
for index, saved in enumerate(saved_textract, start=1):
    job_id = saved["job_id"]
    job_response = httpx.get(f"{BASE}/api/v1/documents/textract/jobs/{job_id}", headers=headers, timeout=60)
    if job_response.status_code != 200:
        failures.append(f"{saved['email']}: job HTTP {job_response.status_code}: {job_response.text}")
        continue
    job = job_response.json()
    actual_items = [
        (item["model_number"], item["article_number"], item["quantity"], item["position"])
        for item in job["lesnina_mapping"]["items"]
    ]
    expected_items = [
        (item["model_number"], item["article_number"], item["quantity"], item["position"])
        for item in saved["mapping"]["items"]
    ]
    if actual_items != expected_items:
        failures.append(f"{saved['email']}: live Textract mapping differs from visually verified mapping")

    email_path = ROOT / "Lesnina" / saved["email"]
    with email_path.open("rb") as source:
        merge_response = httpx.post(
            f"{BASE}/api/v1/documents/textract/jobs/{job_id}/lesnina-orders",
            headers=headers,
            files={"email_file": (email_path.name, source, "message/rfc822")},
            timeout=60,
        )
    if merge_response.status_code != 200:
        failures.append(f"{saved['email']}: plural merge HTTP {merge_response.status_code}: {merge_response.text}")
        continue
    merged = merge_response.json()
    merged_items = [
        (item["model_number"], item["article_number"], item["quantity"], item["position"])
        for order_mapping in merged["orders"]
        for item in order_mapping["order"]["items"]
    ]
    if merged_items != expected_items:
        failures.append(f"{saved['email']}: merged commission items differ from visually verified mapping")
    for order_mapping in merged["orders"]:
        order = order_mapping["order"]
        for field in ("store_address", "delivery_address", "preferred_delivery_week", "commission_number"):
            if not order.get(field):
                failures.append(f"{saved['email']} / {order['commission_number']}: merged order missing {field}")
        if not order["items"]:
            failures.append(f"{saved['email']} / {order['commission_number']}: merged order has no items")
    textract_results.append(
        {
            "index": index,
            "email": saved["email"],
            "job_status": job["status"],
            "orders": len(merged["orders"]),
            "items": len(merged_items),
            "requires_review": merged["requires_review"],
        }
    )

report = {"emails": email_results, "textract": textract_results, "failures": failures}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"EMAIL_HTTP_OK={len(email_results)}/{len(email_paths)}")
print(f"TEXTRACT_AND_MERGE_OK={len(textract_results)}/{len(saved_textract)}")
print(f"FAILURES={len(failures)}")
for failure in failures:
    print(f"FAIL | {failure}")
print(f"REPORT={OUT}")
raise SystemExit(1 if failures else 0)

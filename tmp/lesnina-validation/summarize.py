import json
from pathlib import Path

reports = json.loads(Path(__file__).with_name("results.json").read_text(encoding="utf-8"))
for report in reports:
    preview_order = report["email_preview"]["orders"][0]
    mapping = report.get("mapping", {})
    print("=" * 80)
    print(report["email_name"])
    print(
        f"pages={report['page_count']} tables={report.get('table_count')} lines={report.get('line_count')} "
        f"commission={preview_order['commission_number']} week={preview_order['preferred_delivery_week']}"
    )
    print(f"delivery={preview_order['delivery_address']} name={preview_order['commission_name']}")
    print(f"review={mapping.get('requires_review')} issues={mapping.get('issues')}")
    for item in mapping.get("items", []):
        print(
            f"  {item['position']} | {item['model_number']} | {item['article_number']} | "
            f"qty={item['quantity']} | confidence={item['confidence']:.1f}% | review={item['requires_review']}"
        )
        if item["review_reasons"]:
            print(f"    reasons={item['review_reasons']}")

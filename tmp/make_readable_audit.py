from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = json.loads((ROOT / "tmp" / "corpus-audit" / "audit.json").read_text(encoding="utf-8"))
OUT = ROOT / "tmp" / "corpus-audit" / "readable-audit.txt"


def relevant_body_lines(body: str) -> list[str]:
    patterns = (
        r"^\s*(?:Filiale|Anlieferung|Liefertermin|Komm|Lagerbestellung)\s*:",
        r"^\s*\d+(?:[.,]\d+)?\s*x\s+",
        r"^\s*\d+(?:[.,]\d+)?\s+",
        r"\b(?:TYP|TIP|MOD)\s*:",
        r"^\s*[A-Z0-9]+[/\-][A-Z0-9]+",
        r"Übersetzung zu oben",
        r"Details zur Bestellung",
        r"Detaily k objedn",
    )
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in body.splitlines()
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns)
    ]


lines: list[str] = []
for record in AUDIT["records"]:
    preview = record["preview"]
    lines.extend(
        [
            "=" * 120,
            f"[{record['index']:03d}] {record['folder']} / {record['filename']}",
            f"TYPE={preview['message_type']} PROFILE={preview['client_profile']} ACTION={preview['next_action']}",
            "ATTACHMENTS=" + ", ".join(item["name"] for item in record["attachments"]),
        ]
    )
    if preview["message_type"] == "order":
        lines.append("SOURCE EVIDENCE:")
        lines.extend(f"  {line}" for line in relevant_body_lines(record["body"]))
        for attachment in record["attachments"]:
            if not attachment["name"].casefold().endswith(".xml"):
                continue
            try:
                root = ET.fromstring(Path(attachment["path"]).read_bytes())
            except ET.ParseError:
                lines.append(f"  XML_PARSE_ERROR {attachment['name']}")
                continue
            for head in root.findall(".//HEAD"):
                lines.append(
                    "  XML ORDER "
                    + repr(
                        {
                            "number": head.findtext("OrderNumber"),
                            "commission": head.findtext("Commission"),
                            "week": head.findtext("RequestedDeliveryDate"),
                            "items": [
                                {
                                    "position": node.findtext("LineItemNumber"),
                                    "series": node.findtext("SeriesNumber"),
                                    "article": node.findtext("ProductNumber"),
                                    "quantity": node.findtext("OrderQuantity"),
                                }
                                for node in head.findall("LINE")
                            ],
                        }
                    )
                )
        lines.append("PARSED:")
        for order in preview["orders"]:
            lines.append(
                "  ORDER "
                + repr(
                    {
                        "store": order["store_address"],
                        "delivery": order["delivery_address"],
                        "week": order["preferred_delivery_week"],
                        "name": order["commission_name"],
                        "number": order["commission_number"],
                        "items": [
                            (item["model_number"], item["article_number"], item["quantity"], item["position"])
                            for item in order["items"]
                        ],
                    }
                )
            )
    else:
        clean_body = " ".join(re.sub(r"\s+", " ", record["body"]).split())
        lines.append(f"BODY_START={clean_body[:600]}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(OUT)

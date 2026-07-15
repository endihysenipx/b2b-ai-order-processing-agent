from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
AUDIT = json.loads((ROOT / "tmp" / "corpus-audit" / "audit.json").read_text(encoding="utf-8"))
RESULTS = json.loads((ROOT / "tmp" / "corpus-audit" / "lesnina-textract.json").read_text(encoding="utf-8"))
PAGES = ROOT / "tmp" / "corpus-audit" / "lesnina-pages"
OUT = ROOT / "tmp" / "corpus-audit" / "lesnina-order-sheets"
OUT.mkdir(parents=True, exist_ok=True)

index_by_filename = {record["filename"]: record["index"] for record in AUDIT["records"]}
code_pattern = re.compile(r"[A-Z0-9]+-[A-Z0-9]+")
selected = []
for result in RESULTS:
    table_page = None
    for table in result.get("tables", []):
        if any(code_pattern.search(cell["text"].replace(" ", "")) for cell in table["cells"]):
            table_page = table["page"]
            break
    if table_page is None:
        raise RuntimeError(f"No order table page for {result['email']}")
    index = index_by_filename[result["email"]]
    attachment_stem = next(
        path.stem.rsplit("_p", 1)[0] for path in PAGES.glob(f"{index:03d}_*_p{table_page:02d}.png")
    )
    page_path = PAGES / f"{attachment_stem}_p{table_page:02d}.png"
    selected.append((result["email"].split(" Bestellung", 1)[0], table_page, page_path))

canvas_width = 1800
canvas_height = 2570
label_height = 55
for offset in range(0, len(selected), 2):
    group = selected[offset : offset + 2]
    sheet = Image.new("RGB", (canvas_width * len(group), canvas_height + label_height), "white")
    draw = ImageDraw.Draw(sheet)
    for column, (label, page_number, page_path) in enumerate(group):
        with Image.open(page_path) as page:
            rendered = ImageOps.contain(page.convert("RGB"), (canvas_width - 10, canvas_height - 10))
        x = column * canvas_width + (canvas_width - rendered.width) // 2
        sheet.paste(rendered, (x, label_height))
        draw.text((column * canvas_width + 10, 15), f"{label} - TIFF page {page_number}", fill="black")
    sheet.save(OUT / f"orders-{offset // 2 + 1:02d}.png")

print(f"ORDERS={len(selected)} SHEETS={len(list(OUT.glob('*.png')))}")

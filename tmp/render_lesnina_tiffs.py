from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tmp" / "corpus-audit" / "attachments"
OUT = ROOT / "tmp" / "corpus-audit" / "lesnina-pages"
SHEETS = ROOT / "tmp" / "corpus-audit" / "lesnina-sheets"
OUT.mkdir(parents=True, exist_ok=True)
SHEETS.mkdir(parents=True, exist_ok=True)

first_pages: list[tuple[str, Image.Image]] = []
for source in sorted(SOURCE.glob("*.TIF")):
    with Image.open(source) as image:
        for frame_index in range(image.n_frames):
            image.seek(frame_index)
            page = image.convert("L")
            output = OUT / f"{source.stem}_p{frame_index + 1:02d}.png"
            page.save(output)
            if frame_index == 0:
                first_pages.append((source.stem, page.copy()))

thumb_width = 620
thumb_height = 920
label_height = 44
for sheet_index in range(0, len(first_pages), 4):
    group = first_pages[sheet_index : sheet_index + 4]
    sheet = Image.new("RGB", (thumb_width * len(group), thumb_height + label_height), "white")
    draw = ImageDraw.Draw(sheet)
    for column, (label, page) in enumerate(group):
        thumb = ImageOps.contain(page.convert("RGB"), (thumb_width - 10, thumb_height - 10))
        x = column * thumb_width + (thumb_width - thumb.width) // 2
        sheet.paste(thumb, (x, label_height))
        draw.text((column * thumb_width + 8, 12), label, fill="black")
    sheet.save(SHEETS / f"first-pages-{sheet_index // 4 + 1:02d}.png")

print(f"TIFFS={len(first_pages)}")
print(f"PAGES={len(list(OUT.glob('*.png')))}")
print(f"SHEETS={len(list(SHEETS.glob('*.png')))}")

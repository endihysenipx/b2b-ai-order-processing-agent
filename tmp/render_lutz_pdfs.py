from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tmp" / "corpus-audit" / "attachments"
OUTPUT = ROOT / "tmp" / "corpus-audit" / "lutz-pdf-pages"
SHEETS = ROOT / "tmp" / "corpus-audit" / "lutz-pdf-sheets"
PDFTOPPM = Path(
    r"C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime"
    r"\dependencies\native\poppler\Library\bin\pdftoppm.exe"
)


def render() -> list[tuple[Path, int, Path]]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rendered: list[tuple[Path, int, Path]] = []
    for pdf in sorted(SOURCE.rglob("*.pdf")):
        prefix = OUTPUT / pdf.stem
        subprocess.run(
            [str(PDFTOPPM), "-jpeg", "-r", "110", str(pdf), str(prefix)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        for page_path in sorted(OUTPUT.glob(f"{pdf.stem}-*.jpg")):
            page = int(page_path.stem.rsplit("-", 1)[1])
            rendered.append((pdf, page, page_path))
    return rendered


def make_sheets(rendered: list[tuple[Path, int, Path]]) -> None:
    SHEETS.mkdir(parents=True, exist_ok=True)
    cell_w, cell_h = 900, 700
    for sheet_number, start in enumerate(range(0, len(rendered), 4), 1):
        canvas = Image.new("RGB", (cell_w * 2, cell_h * 2), "white")
        draw = ImageDraw.Draw(canvas)
        for slot, (pdf, page, image_path) in enumerate(rendered[start : start + 4]):
            image = Image.open(image_path).convert("RGB")
            image.thumbnail((cell_w - 20, cell_h - 55))
            image = ImageOps.expand(image, border=1, fill="black")
            x = (slot % 2) * cell_w + (cell_w - image.width) // 2
            y = (slot // 2) * cell_h + 42
            canvas.paste(image, (x, y))
            label = f"{pdf.name} — page {page}"
            draw.text(((slot % 2) * cell_w + 10, (slot // 2) * cell_h + 12), label, fill="black")
        canvas.save(SHEETS / f"pdf-pages-{sheet_number:02d}.jpg", quality=90)


if __name__ == "__main__":
    pages = render()
    make_sheets(pages)
    print(f"Rendered {len(pages)} pages from {len(list(SOURCE.rglob('*.pdf')))} PDFs")
    print(f"Created {len(list(SHEETS.glob('*.jpg')))} contact sheets")

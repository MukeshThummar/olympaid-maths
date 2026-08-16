"""Quick script to render sample pages from the PDF as PNG for inspection."""
import sys
sys.path.insert(0, ".")

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from pathlib import Path

PDF_PATH = "docs/Maths Olympiad workbook.pdf"
OUT_DIR = Path("sample_pages")
OUT_DIR.mkdir(exist_ok=True)

doc = fitz.open(PDF_PATH)
print(f"Total pages: {doc.page_count}")

# Render pages 1, 5, 10, 20, 40 as PNG for inspection
sample_pages = [0, 1, 4, 9, 19, 39]
for pn in sample_pages:
    if pn >= doc.page_count:
        continue
    page = doc[pn]
    mat = fitz.Matrix(2.0, 2.0)   # 2x zoom = ~144 DPI
    pix = page.get_pixmap(matrix=mat)
    out_path = OUT_DIR / f"page_{pn+1:03d}.png"
    pix.save(str(out_path))
    print(f"  Saved {out_path} ({out_path.stat().st_size // 1024} KB)")

doc.close()
print("Done.")

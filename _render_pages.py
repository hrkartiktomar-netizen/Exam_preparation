import sys, os

pdf_path = sys.argv[1]
out_dir = sys.argv[2]
dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 170

os.makedirs(out_dir, exist_ok=True)
n = None
try:
    import pymupdf
    doc = pymupdf.open(pdf_path)
    zoom = dpi / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    n = doc.page_count
    print(f"pages={n}")
    for i in range(n):
        pix = doc[i].get_pixmap(matrix=mat, alpha=False)
        pix.save(os.path.join(out_dir, f"page_{i+1:04d}.png"))
    print("rendered", n, "pages at", dpi, "dpi to", out_dir, "(engine=pymupdf)")
except Exception as e:
    print("pymupdf failed:", e, "- trying pypdfium2")
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf_path)
    n = len(doc)
    print(f"pages={n}")
    scale = dpi / 72.0
    for i in range(n):
        page = doc[i]
        bmp = page.render(scale=scale)
        img = bmp.to_pil()
        img.save(os.path.join(out_dir, f"page_{i+1:04d}.png"))
    print("rendered", n, "pages at", dpi, "dpi to", out_dir, "(engine=pypdfium2)")

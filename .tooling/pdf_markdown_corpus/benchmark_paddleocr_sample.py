from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import fitz
from PIL import Image
from paddleocr import PaddleOCR


def render_page(pdf_path: Path, page_index: int, output_path: Path, dpi: int = 220) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        image.save(output_path)
    finally:
        doc.close()
    return output_path


def normalize_result(result):
    if hasattr(result, "json"):
        return result.json
    if hasattr(result, "to_dict"):
        return result.to_dict()
    if isinstance(result, dict):
        return result
    return result


def extract_lines(result_obj) -> list[str]:
    data = normalize_result(result_obj)
    lines: list[str] = []

    if isinstance(data, dict):
        for key in ("rec_texts", "text", "texts"):
            value = data.get(key)
            if isinstance(value, list):
                lines.extend(str(item) for item in value if str(item).strip())
            elif isinstance(value, str) and value.strip():
                lines.append(value.strip())
        if lines:
            return lines

        res = data.get("res")
        if isinstance(res, dict):
            value = res.get("rec_texts")
            if isinstance(value, list):
                lines.extend(str(item) for item in value if str(item).strip())
            if lines:
                return lines

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                lines.extend(extract_lines(item))
            elif isinstance(item, (list, tuple)):
                for child in item:
                    if isinstance(child, (list, tuple)) and child:
                        maybe_text = child[0] if isinstance(child[0], str) else None
                        if maybe_text:
                            lines.append(maybe_text)
                    elif isinstance(child, str):
                        lines.append(child)

    return [line for line in lines if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, default=1, help="1-based page number")
    parser.add_argument("--out-dir", type=Path, default=Path(r"D:\Exam_preparation\.tooling\pdf_markdown_corpus\paddleocr_test"))
    parser.add_argument("--dpi", type=int, default=220)
    args = parser.parse_args()

    out_dir = args.out_dir / args.pdf.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    image_path = out_dir / f"page_{args.page:03d}.png"
    render_page(args.pdf, args.page - 1, image_path, dpi=args.dpi)

    init_started = time.perf_counter()
    ocr = PaddleOCR(
        lang="en",
        ocr_version="PP-OCRv6",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )
    init_seconds = time.perf_counter() - init_started

    predict_started = time.perf_counter()
    results = ocr.predict(str(image_path))
    predict_seconds = time.perf_counter() - predict_started

    normalized = [normalize_result(item) for item in results]
    lines: list[str] = []
    for item in results:
        lines.extend(extract_lines(item))

    payload = {
        "pdf": str(args.pdf),
        "page": args.page,
        "image": str(image_path),
        "dpi": args.dpi,
        "init_seconds": round(init_seconds, 3),
        "predict_seconds": round(predict_seconds, 3),
        "line_count": len(lines),
        "lines": lines,
        "raw": normalized,
    }

    (out_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in payload if k != "raw"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

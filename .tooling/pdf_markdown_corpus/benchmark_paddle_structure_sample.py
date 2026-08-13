from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import fitz
from PIL import Image
from paddleocr import PPStructureV3


def render_page(pdf_path: Path, page_index: int, output_path: Path, dpi: int = 220) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        Image.frombytes("RGB", [pix.width, pix.height], pix.samples).save(output_path)
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


def collect_markdown(results) -> str:
    parts: list[str] = []
    for result in results:
        data = normalize_result(result)
        if isinstance(data, dict):
            for key in ("markdown", "md", "markdown_text"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
            res = data.get("res")
            if isinstance(res, dict):
                for key in ("markdown", "md", "markdown_text"):
                    value = res.get(key)
                    if isinstance(value, str) and value.strip():
                        parts.append(value.strip())
                markdown = res.get("markdown")
                if isinstance(markdown, dict):
                    value = markdown.get("markdown_text")
                    if isinstance(value, str) and value.strip():
                        parts.append(value.strip())
    return "\n\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, default=1, help="1-based page number")
    parser.add_argument("--out-dir", type=Path, default=Path(r"D:\Exam_preparation\.tooling\pdf_markdown_corpus\paddle_structure_test"))
    parser.add_argument("--dpi", type=int, default=220)
    args = parser.parse_args()

    out_dir = args.out_dir / args.pdf.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    image_path = out_dir / f"page_{args.page:03d}.png"
    render_page(args.pdf, args.page - 1, image_path, dpi=args.dpi)

    init_started = time.perf_counter()
    pipeline = PPStructureV3(
        lang="en",
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        use_seal_recognition=False,
        use_formula_recognition=False,
        use_chart_recognition=False,
        use_region_detection=False,
        use_table_recognition=True,
        format_block_content=True,
    )
    init_seconds = time.perf_counter() - init_started

    predict_started = time.perf_counter()
    results = list(
        pipeline.predict(
            str(image_path),
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            use_seal_recognition=False,
            use_formula_recognition=False,
            use_chart_recognition=False,
            use_region_detection=False,
            use_table_recognition=True,
            format_block_content=True,
        )
    )
    predict_seconds = time.perf_counter() - predict_started

    normalized = [normalize_result(item) for item in results]
    markdown = collect_markdown(results)

    payload = {
        "pdf": str(args.pdf),
        "page": args.page,
        "image": str(image_path),
        "dpi": args.dpi,
        "init_seconds": round(init_seconds, 3),
        "predict_seconds": round(predict_seconds, 3),
        "markdown_chars": len(markdown),
        "markdown": markdown,
        "raw": normalized,
    }
    (out_dir / "result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "result.md").write_text(markdown + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in payload if k != "raw"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


DEFAULT_OCR_DIR = Path(r"D:\Exam_preparation\.tooling\pdf_markdown_corpus\gemini_ocr")
DEFAULT_OUTPUT_DIR = Path(r"D:\Exam_preparation\.tooling\pdf_markdown_corpus\gemini_ocr_merged")


PAGE_RE = re.compile(r"page_(\d{4})\.json$")


def load_records(ocr_dir: Path) -> list[dict]:
    records: list[dict] = []
    for json_path in sorted(ocr_dir.glob("**/page_*.json")):
        match = PAGE_RE.search(json_path.name)
        if not match:
            continue
        record = json.loads(json_path.read_text(encoding="utf-8"))
        md_path = Path(record["markdown"])
        if not md_path.exists():
            continue
        record["markdown_text"] = md_path.read_text(encoding="utf-8").strip()
        records.append(record)
    return records


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE)
    return stem[:160]


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge Gemini OCR page Markdown into per-PDF Markdown files.")
    parser.add_argument("--ocr-dir", type=Path, default=DEFAULT_OCR_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    records = load_records(args.ocr_dir)
    by_pdf: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_pdf[record["pdf_name"]].append(record)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    index_lines = ["# Gemini OCR Merged Index", ""]
    for pdf_name, pdf_records in sorted(by_pdf.items()):
        pdf_records = sorted(pdf_records, key=lambda item: item["page"])
        out_path = args.out_dir / f"{safe_stem(pdf_name)}.md"
        lines = [f"# {pdf_name}", ""]
        for record in pdf_records:
            lines.append(f"## Page {record['page']}")
            lines.append("")
            lines.append(record["markdown_text"] or "[empty OCR output]")
            lines.append("")
        out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        index_lines.append(f"- `{pdf_name}`: {len(pdf_records)} pages -> `{out_path}`")

    index_path = args.out_dir / "_index.md"
    index_path.write_text("\n".join(index_lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"merged_documents": len(by_pdf), "merged_pages": len(records), "index": str(index_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

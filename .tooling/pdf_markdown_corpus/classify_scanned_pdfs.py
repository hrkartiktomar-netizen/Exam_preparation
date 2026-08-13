from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz


WORD_RE = re.compile(r"\w+", re.UNICODE)


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {item.get("name", Path(item.get("path", "")).name): item for item in data}
    if isinstance(data, dict):
        return {Path(k).name: v for k, v in data.items()}
    return {}


def rect_area(bbox: Any, page_rect: fitz.Rect) -> float:
    try:
        rect = fitz.Rect(bbox) & page_rect
    except Exception:
        return 0.0
    if rect.is_empty or rect.is_infinite:
        return 0.0
    return max(rect.width, 0.0) * max(rect.height, 0.0)


def page_image_stats(page: fitz.Page) -> tuple[int, float, float]:
    page_rect = page.rect
    page_area = max(page_rect.width * page_rect.height, 1.0)
    areas: list[float] = []

    try:
        for info in page.get_image_info(xrefs=True):
            bbox = info.get("bbox")
            if bbox:
                areas.append(rect_area(bbox, page_rect))
    except Exception:
        areas = []

    if not areas:
        try:
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") == 1:
                    areas.append(rect_area(block.get("bbox"), page_rect))
        except Exception:
            areas = []

    total_coverage = min(sum(areas) / page_area, 1.0)
    largest_coverage = max(areas, default=0.0) / page_area
    return len(areas), round(total_coverage, 4), round(largest_coverage, 4)


def classify_page(text_chars: int, word_count: int, image_count: int, image_coverage: float, largest_image_coverage: float) -> str:
    if text_chars < 50 and image_coverage < 0.12:
        return "blank_or_decorative"
    if text_chars < 100 and (image_coverage >= 0.55 or largest_image_coverage >= 0.50):
        return "image_only_scan_ocr_required"
    if text_chars < 250 and image_coverage >= 0.28:
        return "sparse_image_page_ocr_recommended"
    if word_count >= 20 and (image_coverage >= 0.70 or largest_image_coverage >= 0.65):
        return "image_backed_with_text_layer"
    return "text_native_or_light_image"


def classify_pdf(counter: Counter[str], total_pages: int) -> str:
    if total_pages == 0:
        return "unreadable"

    ocr_required = counter["image_only_scan_ocr_required"] + counter["sparse_image_page_ocr_recommended"]
    image_backed = ocr_required + counter["image_backed_with_text_layer"]

    if ocr_required / total_pages >= 0.80:
        return "scan_based_needs_full_ocr"
    if ocr_required / total_pages >= 0.30:
        return "partially_scan_based_ocr_needed"
    if counter["image_backed_with_text_layer"] / total_pages >= 0.50:
        return "image_backed_text_layer_verify_ocr"
    if ocr_required > 0:
        return "some_scanned_pages_ocr_needed"
    if image_backed / total_pages >= 0.30:
        return "image_heavy_layout_verify_reading_order"
    return "text_native_or_light_image"


def analyze_pdf(path: Path, manifest_by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": path.name,
        "path": str(path),
        "bytes": path.stat().st_size,
        "error": None,
        "pages": 0,
        "classification": "unreadable",
        "page_class_counts": {},
        "ocr_required_pages": [],
        "image_backed_pages": [],
        "blank_or_decorative_pages": [],
        "sample_pages": [],
        "manifest_low_text_pages": [],
        "manifest_ocr_pages": [],
    }

    manifest = manifest_by_name.get(path.name, {})
    result["manifest_low_text_pages"] = manifest.get("low_text_pages", [])
    result["manifest_ocr_pages"] = manifest.get("ocr_pages", [])
    result["manifest_word_count_ocr_augmented"] = manifest.get("word_count_ocr_augmented")
    result["manifest_text_file_ocr_augmented"] = manifest.get("text_file_ocr_augmented")

    try:
        doc = fitz.open(path)
    except Exception as exc:
        result["error"] = repr(exc)
        result["classification"] = "open_error"
        return result

    counter: Counter[str] = Counter()
    text_chars_total = 0
    word_count_total = 0
    coverage_sum = 0.0
    largest_coverage_max = 0.0

    try:
        result["pages"] = doc.page_count
        for idx in range(doc.page_count):
            page = doc.load_page(idx)
            text = page.get_text("text") or ""
            clean_text = text.strip()
            text_chars = len(clean_text)
            word_count = len(WORD_RE.findall(clean_text))
            image_count, image_coverage, largest_image_coverage = page_image_stats(page)
            page_class = classify_page(
                text_chars=text_chars,
                word_count=word_count,
                image_count=image_count,
                image_coverage=image_coverage,
                largest_image_coverage=largest_image_coverage,
            )

            page_no = idx + 1
            counter[page_class] += 1
            text_chars_total += text_chars
            word_count_total += word_count
            coverage_sum += image_coverage
            largest_coverage_max = max(largest_coverage_max, largest_image_coverage)

            if page_class in {"image_only_scan_ocr_required", "sparse_image_page_ocr_recommended"}:
                result["ocr_required_pages"].append(page_no)
            if page_class in {
                "image_only_scan_ocr_required",
                "sparse_image_page_ocr_recommended",
                "image_backed_with_text_layer",
            }:
                result["image_backed_pages"].append(page_no)
            if page_class == "blank_or_decorative":
                result["blank_or_decorative_pages"].append(page_no)

            if page_class != "text_native_or_light_image" and len(result["sample_pages"]) < 12:
                result["sample_pages"].append(
                    {
                        "page": page_no,
                        "class": page_class,
                        "text_chars": text_chars,
                        "words": word_count,
                        "image_count": image_count,
                        "image_coverage": image_coverage,
                        "largest_image_coverage": largest_image_coverage,
                    }
                )
    except Exception as exc:
        result["error"] = repr(exc)
    finally:
        doc.close()

    result["page_class_counts"] = dict(counter)
    result["classification"] = classify_pdf(counter, result["pages"])
    result["text_chars"] = text_chars_total
    result["word_count"] = word_count_total
    result["avg_image_coverage"] = round(coverage_sum / result["pages"], 4) if result["pages"] else 0.0
    result["max_largest_image_coverage"] = round(largest_coverage_max, 4)
    result["ocr_required_page_count"] = len(result["ocr_required_pages"])
    result["image_backed_page_count"] = len(result["image_backed_pages"])
    result["blank_or_decorative_page_count"] = len(result["blank_or_decorative_pages"])
    return result


def page_list_short(pages: list[int], limit: int = 18) -> str:
    if not pages:
        return "-"
    shown = ", ".join(str(p) for p in pages[:limit])
    if len(pages) > limit:
        shown += f", ... (+{len(pages) - limit})"
    return shown


def write_markdown(results: list[dict[str, Any]], output_path: Path, pdf_dir: Path) -> None:
    class_counts = Counter(item["classification"] for item in results)
    total_pages = sum(item.get("pages", 0) for item in results)
    total_ocr_required = sum(item.get("ocr_required_page_count", 0) for item in results)
    total_image_backed = sum(item.get("image_backed_page_count", 0) for item in results)

    priority = {
        "scan_based_needs_full_ocr": 0,
        "partially_scan_based_ocr_needed": 1,
        "some_scanned_pages_ocr_needed": 2,
        "image_backed_text_layer_verify_ocr": 3,
        "image_heavy_layout_verify_reading_order": 4,
        "text_native_or_light_image": 5,
        "open_error": 6,
        "unreadable": 7,
    }

    sorted_results = sorted(
        results,
        key=lambda item: (
            priority.get(item["classification"], 99),
            -item.get("ocr_required_page_count", 0),
            -item.get("image_backed_page_count", 0),
            item["name"].lower(),
        ),
    )

    lines: list[str] = []
    lines.append("# PDF Scan Classification")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- PDF directory: `{pdf_dir}`")
    lines.append(f"- PDFs checked: {len(results)}")
    lines.append(f"- Pages checked: {total_pages}")
    lines.append(f"- OCR-required pages detected: {total_ocr_required}")
    lines.append(f"- Image-backed pages detected: {total_image_backed}")
    lines.append("")
    lines.append("## Classification Counts")
    lines.append("")
    for name, count in sorted(class_counts.items(), key=lambda pair: (priority.get(pair[0], 99), pair[0])):
        lines.append(f"- `{name}`: {count}")
    lines.append("")
    lines.append("## OCR Priority")
    lines.append("")
    lines.append("| Classification | PDF | Pages | OCR-required | Image-backed | Avg image coverage | Pages to inspect |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for item in sorted_results:
        if item["classification"] == "text_native_or_light_image":
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{item['classification']}`",
                    item["name"].replace("|", "\\|"),
                    str(item.get("pages", 0)),
                    str(item.get("ocr_required_page_count", 0)),
                    str(item.get("image_backed_page_count", 0)),
                    str(item.get("avg_image_coverage", 0.0)),
                    page_list_short(item.get("ocr_required_pages", []) or item.get("image_backed_pages", [])),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Fully Text-Native Or Light-Image PDFs")
    lines.append("")
    text_native = [item for item in sorted_results if item["classification"] == "text_native_or_light_image"]
    for item in text_native:
        lines.append(f"- `{item['name']}` ({item.get('pages', 0)} pages, {item.get('word_count', 0)} words)")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify text-native vs scanned/image-backed PDFs.")
    parser.add_argument("--pdf-dir", type=Path, default=Path(r"D:\Exam_preparation\source_documents\pdfs"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(r"D:\Exam_preparation\.tooling\pdf_direct_read\manifest_ocr_augmented.json"),
    )
    parser.add_argument("--out-json", type=Path, default=Path("scan_classification.json"))
    parser.add_argument("--out-md", type=Path, default=Path("scan_classification.md"))
    args = parser.parse_args()

    pdf_dir = args.pdf_dir
    manifest = load_manifest(args.manifest)
    pdfs = sorted(pdf_dir.glob("*.pdf"), key=lambda p: p.name.lower())
    results = [analyze_pdf(path, manifest) for path in pdfs]

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "pdf_dir": str(pdf_dir),
        "pdf_count": len(results),
        "page_count": sum(item.get("pages", 0) for item in results),
        "classification_counts": dict(Counter(item["classification"] for item in results)),
        "ocr_required_page_count": sum(item.get("ocr_required_page_count", 0) for item in results),
        "image_backed_page_count": sum(item.get("image_backed_page_count", 0) for item in results),
        "results": results,
    }
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(results, args.out_md, pdf_dir)

    print(json.dumps({k: payload[k] for k in payload if k != "results"}, ensure_ascii=False, indent=2))
    print(f"json={args.out_json.resolve()}")
    print(f"markdown={args.out_md.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

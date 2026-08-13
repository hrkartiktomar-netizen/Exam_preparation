from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz
from google import genai
from google.genai import types


DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_CLASSIFICATION = Path(r"D:\Exam_preparation\.tooling\pdf_markdown_corpus\scan_classification.json")
DEFAULT_OUTPUT_DIR = Path(r"D:\Exam_preparation\.tooling\pdf_markdown_corpus\gemini_ocr")


PROMPT = """Extract this exam-preparation PDF page into clean Markdown.

Rules:
- Return only Markdown, no commentary.
- Preserve all visible study/exam text in reading order.
- Convert tables into Markdown tables where possible.
- Preserve section headings, bullet/numbered lists, dates, figures, percentages, and legal/regulatory names exactly.
- Do not summarize, interpret, correct, or add facts.
- If text is unreadable, write [illegible] at that point.
- If the page is only decorative/blank, return [blank/decorative page].
"""


@dataclass(frozen=True)
class PageJob:
    pdf_path: Path
    pdf_name: str
    page: int


def safe_stem(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE)
    return stem[:160]


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"Env file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ.setdefault(name, value)


def parse_pages(spec: str) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return sorted(set(pages))


def load_jobs_from_classification(path: Path, mode: str) -> list[PageJob]:
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs: list[PageJob] = []
    for item in data["results"]:
        pdf_path = Path(item["path"])
        if mode == "ocr-required":
            pages = item.get("ocr_required_pages", [])
        elif mode == "image-backed":
            pages = item.get("image_backed_pages", [])
        elif mode == "full-scan":
            pages = list(range(1, item.get("pages", 0) + 1)) if item["classification"] == "scan_based_needs_full_ocr" else []
        else:
            raise ValueError(f"Unknown mode: {mode}")
        for page in pages:
            jobs.append(PageJob(pdf_path=pdf_path, pdf_name=item["name"], page=int(page)))
    return jobs


def render_page(pdf_path: Path, page: int, image_path: Path, dpi: int) -> None:
    image_path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    try:
        page_obj = doc.load_page(page - 1)
        pix = page_obj.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False, annots=True)
        pix.save(image_path)
    finally:
        doc.close()


def read_image_part(image_path: Path) -> types.Part:
    data = image_path.read_bytes()
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    return types.Part.from_bytes(data=data, mime_type=mime)


def output_paths(job: PageJob, out_dir: Path) -> tuple[Path, Path, Path]:
    doc_dir = out_dir / safe_stem(job.pdf_name)
    image_path = doc_dir / f"page_{job.page:04d}.png"
    md_path = doc_dir / f"page_{job.page:04d}.md"
    json_path = doc_dir / f"page_{job.page:04d}.json"
    return image_path, md_path, json_path


def discover_api_keys() -> list[str]:
    keys: list[str] = []
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"):
        value = os.getenv(env_name)
        if value:
            keys.append(value)

    numbered: list[tuple[int, str]] = []
    for name, value in os.environ.items():
        match = re.fullmatch(r"GEMINI_API_KEY_(\d+)", name)
        if match and value:
            numbered.append((int(match.group(1)), value))
    keys.extend(value for _, value in sorted(numbered))

    deduped: list[str] = []
    seen: set[str] = set()
    for key in keys:
        if key not in seen:
            deduped.append(key)
            seen.add(key)
    return deduped


def build_client(api_keys: list[str], index: int) -> genai.Client:
    if not api_keys:
        raise SystemExit("Set GEMINI_API_KEY, GOOGLE_API_KEY, or GEMINI_API_KEY_1..N before running cloud OCR.")
    return genai.Client(api_key=api_keys[index % len(api_keys)])


def run_job(client: genai.Client, model: str, job: PageJob, out_dir: Path, dpi: int, force: bool) -> bool:
    image_path, md_path, json_path = output_paths(job, out_dir)
    if md_path.exists() and json_path.exists() and not force:
        return False

    render_page(job.pdf_path, job.page, image_path, dpi)
    response = client.models.generate_content(
        model=model,
        contents=[
            PROMPT,
            read_image_part(image_path),
        ],
    )
    text = response.text or ""
    md_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "pdf": str(job.pdf_path),
                "pdf_name": job.pdf_name,
                "page": job.page,
                "model": model,
                "image": str(image_path),
                "markdown": str(md_path),
                "response_text_chars": len(text),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return True


def run_job_with_key_rotation(
    api_keys: list[str],
    model: str,
    job: PageJob,
    out_dir: Path,
    dpi: int,
    force: bool,
    start_index: int,
    max_key_attempts: int,
    retry_sleep: float,
) -> bool:
    image_path, md_path, json_path = output_paths(job, out_dir)
    if md_path.exists() and json_path.exists() and not force:
        return False

    attempts = min(max_key_attempts or len(api_keys), len(api_keys))
    errors: list[str] = []
    for offset in range(attempts):
        key_index = (start_index + offset) % len(api_keys)
        try:
            client = build_client(api_keys, key_index)
            return run_job(client, model, job, out_dir, dpi, force)
        except Exception as exc:
            errors.append(f"key_slot={key_index + 1}: {type(exc).__name__}: {exc}")
            if retry_sleep and offset + 1 < attempts:
                time.sleep(retry_sleep)

    error_path = json_path.with_suffix(".error.json")
    error_path.parent.mkdir(parents=True, exist_ok=True)
    error_path.write_text(
        json.dumps(
            {
                "pdf": str(job.pdf_path),
                "pdf_name": job.pdf_name,
                "page": job.page,
                "model": model,
                "image": str(image_path),
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    raise RuntimeError(f"All Gemini key attempts failed for {job.pdf_name} page {job.page}. See {error_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render selected PDF pages and OCR them with Gemini into Markdown.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--env-file", type=Path, help="Optional .env file containing GEMINI_API_KEY or GEMINI_API_KEY_1..N.")
    parser.add_argument("--classification", type=Path, default=DEFAULT_CLASSIFICATION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mode", choices=["ocr-required", "image-backed", "full-scan"], default="ocr-required")
    parser.add_argument("--pdf", type=Path, help="Run one PDF instead of the classification list.")
    parser.add_argument("--pages", help="Pages for --pdf, e.g. 1,3,5-7.")
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds between API calls.")
    parser.add_argument("--max-key-attempts", type=int, default=0, help="Number of environment keys to try per page. Default: all.")
    parser.add_argument("--retry-sleep", type=float, default=2.0, help="Seconds to wait before trying the next key after an error.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.env_file:
        load_env_file(args.env_file)

    if args.pdf:
        if not args.pages:
            raise SystemExit("--pages is required with --pdf")
        jobs = [PageJob(pdf_path=args.pdf, pdf_name=args.pdf.name, page=page) for page in parse_pages(args.pages)]
    else:
        jobs = load_jobs_from_classification(args.classification, args.mode)

    if args.limit:
        jobs = jobs[: args.limit]

    print(json.dumps({"model": args.model, "job_count": len(jobs), "mode": args.mode, "out_dir": str(args.out_dir)}, indent=2))
    if args.dry_run:
        for job in jobs[:25]:
            print(f"{job.pdf_name} :: page {job.page}")
        return 0

    api_keys = discover_api_keys()
    completed = 0
    skipped = 0
    for index, job in enumerate(jobs, 1):
        print(f"[{index}/{len(jobs)}] {job.pdf_name} page {job.page}")
        changed = run_job_with_key_rotation(
            api_keys=api_keys,
            model=args.model,
            job=job,
            out_dir=args.out_dir,
            dpi=args.dpi,
            force=args.force,
            start_index=index - 1,
            max_key_attempts=args.max_key_attempts,
            retry_sleep=args.retry_sleep,
        )
        completed += int(changed)
        skipped += int(not changed)
        if args.sleep and index < len(jobs):
            time.sleep(args.sleep)

    print(json.dumps({"completed": completed, "skipped": skipped}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

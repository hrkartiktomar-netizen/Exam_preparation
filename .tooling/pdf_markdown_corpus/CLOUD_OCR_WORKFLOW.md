# Cloud OCR Workflow

This folder contains the OCR tooling for the scan/image-heavy PDF pages.

## Current Decision

- Use `gemini-3.5-flash` for cloud OCR of scanned pages when API keys are available.
- Use the scan classifier output at `scan_classification.json` to avoid sending all 5,802 pages.
- Default target is only `ocr_required_pages`, currently 360 pages.
- Local Marker/Surya remains the best local table-preserving fallback, but it is slow on this CPU-only setup.
- Local PaddleOCR PP-OCRv6 is faster than Marker for plain text OCR, but does not preserve tables as well on the sample page.

## Secret Handling

Do not put API key values in this repository or in command history.

The OCR driver reads keys from environment variables:

- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`
- `GOOGLE_GENAI_API_KEY`
- `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, ... `GEMINI_API_KEY_N`

If multiple numbered keys are present, the script rotates across them page-by-page and retries with the next key on failure.

## Dry Run

```powershell
python .tooling\pdf_markdown_corpus\gemini_page_ocr.py --dry-run --limit 20
```

## Run A Small Sample

```powershell
python .tooling\pdf_markdown_corpus\gemini_page_ocr.py --limit 3 --sleep 1
python .tooling\pdf_markdown_corpus\merge_gemini_ocr_pages.py
```

## Run All OCR-Required Pages

```powershell
python .tooling\pdf_markdown_corpus\gemini_page_ocr.py --mode ocr-required --sleep 1
python .tooling\pdf_markdown_corpus\merge_gemini_ocr_pages.py
```

## Outputs

- Page images and per-page Markdown: `gemini_ocr`
- Merged per-PDF Markdown: `gemini_ocr_merged`
- Scan classification: `scan_classification.md` and `scan_classification.json`

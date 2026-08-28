"""Gemini Flash-Lite OCR engine: PDF -> Markdown with 10-key rotation.

Usage:
  python _ocr_engine.py                 # convert all PDFs not yet converted
  python _ocr_engine.py --only 009      # only files whose name contains pattern
  python _ocr_engine.py --force         # re-convert even if md exists
  python _ocr_engine.py --workers 16    # parallel page workers
"""
import os, re, sys, time, shutil, hashlib, argparse, threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pymupdf
from google.genai import Client, types

ROOT = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(ROOT, "source_documents", "pdfs")
MD_DIR = os.path.join(ROOT, "source_documents", "md")
CACHE = os.path.join(ROOT, "_ocr_cache")
PROGRESS = os.path.join(ROOT, "_ocr_progress.tsv")
DPI = int(os.environ.get("OCR_DPI", "200"))

# Roll-number-only result lists: user instructed these have no study value.
SKIP = {
    "008_IFSCA career__2025 Phase 1 Results - General Stream.pdf",
    "discovered_008_IFSCA-Grade-A-2025-Phase-1-result.pdf",
    "012_IFSCA career__202526 Phase 2 Results.pdf",
    "discovered_009_IFSCA-Grade-A-2025-Phase-2-result.pdf",
    "discovered_010_IFSCA-Grade-A-2025-final-result.pdf",
}

SYSTEM_PROMPT = (
    "You are VeraOCR, a forensic-grade document transcription engine. You output ONLY a "
    "faithful Markdown transcription of the page image provided. You never summarize, never "
    "paraphrase, never omit, never invent, and never add commentary."
)

USER_PROMPT = """Transcribe this scanned page VERBATIM into GitHub-Flavored Markdown.

STRICT RULES (violation = failure):
1. Output ONLY the transcription. No preamble, no closing notes, no ``` fences around the whole output.
2. Preserve exact visual reading order and ALL content: every word, number, symbol, heading, footnote, header/footer line, table cell, list item, form blank and seal/stamp text that is legible.
3. Headings: use #/##/### to match the visual hierarchy; keep original capitalization and punctuation.
4. Tables: render as GFM markdown tables with exactly the same rows and columns; keep cell text exact; leave empty cells empty; join multi-line cell text with a single space.
5. Lists: preserve the original numbering/lettering/bullet style exactly (e.g. "(i)", "a.", "5.", "•", "-").
6. Emphasis: **bold** where the print is bold, *italics* where italic or underlined.
7. Transcribe Hindi/Devanagari and any other scripts verbatim in the original script.
8. Numbers, dates, currency, percentages exactly as printed (Rs., ₹, %, 11.02.2023, 1,43,000). Do NOT normalize, correct or round.
9. Preserve original typos exactly as printed. Do not fix spelling.
10. If a region is genuinely illegible, output [illegible: brief description] in place. NEVER guess text.
11. Do not add page numbers or markers; the pipeline adds them.
12. NEVER invent or output URLs, hyperlinks, or image markdown (![...](...)). For logos, seals, stamps or photographs render a plain-text placeholder like [logo: IFSCA] or [seal] — never a fabricated link."""

NUMBERED_PROMPT = USER_PROMPT + (
    "\n13. ANTI-RECITATION FORMAT: prefix EVERY output line with its 3-digit sequential line "
    "number followed by colon and space (e.g. \"001: \"); for blank transcription lines output "
    "just the number and colon. The transcription itself must remain completely verbatim — "
    "only the numeric line prefix is added."
)


def unnumber(t):
    return "\n".join(re.sub(r"^\s*\d{1,4}:\s?", "", line) for line in t.split("\n")).strip()


def load_env():
    env = dict(os.environ)
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def collect_keys(env):
    keys = []
    if env.get("GEMINI_API_KEYS"):
        keys += [k.strip() for k in re.split("[,;]", env["GEMINI_API_KEYS"]) if k.strip()]
    for i in range(1, 31):
        v = env.get(f"GEMINI_KEY_{i}")
        if v and "here" not in v and len(v) > 10:
            keys.append(v)
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


class KeyPool:
    def __init__(self, keys):
        self.keys = keys
        self.lock = threading.Lock()
        self.idx = 0
        self.cooldown = {k: 0.0 for k in keys}
        self.disabled = set()
        self.usage = {k: 0 for k in keys}

    def get(self):
        while True:
            with self.lock:
                now = time.time()
                for _ in range(len(self.keys)):
                    k = self.keys[self.idx % len(self.keys)]
                    self.idx += 1
                    if k in self.disabled or self.cooldown[k] > now:
                        continue
                    self.usage[k] += 1
                    return k
                wake = min([self.cooldown[k] for k in self.keys if k not in self.disabled], default=now + 30)
            time.sleep(max(0.5, min(30, wake - time.time() + 0.5)))

    def report(self, key, err=None):
        with self.lock:
            if err is None:
                return
            s = str(err).lower()
            if "quota" in s or "resource_exhausted" in s or "429" in s or "rate" in s or "403" in s:
                # 403 here is usually quota-exceeded, not an auth problem
                self.cooldown[key] = time.time() + 60
            elif "api key not valid" in s or "api_key_invalid" in s or "401" in s or "permission denied" in s:
                print(f"  [pool] disabling key ...{key[-4:]} (auth error)", flush=True)
                self.disabled.add(key)
                if len(self.disabled) == len(self.keys):
                    raise SystemExit("All API keys disabled. Check .env.")
            else:
                self.cooldown[key] = time.time() + 10


def classify_and_sleep(err, attempt):
    time.sleep(min(30, 1.5 * attempt))


def resolve_model(pool, preferred):
    client = Client(api_key=pool.get())
    names = set()
    try:
        for m in client.models.list():
            names.add(m.name.split("/")[-1])
    except Exception as e:
        print(f"  [model] list failed ({e}); using preferred name", flush=True)
        return preferred[0]
    for cand in preferred:
        if cand in names:
            return cand
    for frag in ("3.5-flash-lite", "3-flash-lite", "2.5-flash-lite", "flash-lite", "flash"):
        for n in sorted(names):
            if frag in n and "image" not in n:
                return n
    return preferred[0]


def transcribe_page(pool, model, png_path, page_no, n_pages, max_rounds):
    data = open(png_path, "rb").read()
    quote = False
    empties = 0
    quota_hits = 0
    last_fr = ""
    for attempt in range(1, max_rounds + 1):
        key = pool.get()
        try:
            client = Client(api_key=key, http_options=types.HttpOptions(timeout=600_000))
            prompt = NUMBERED_PROMPT if quote else USER_PROMPT
            resp = client.models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=data, mime_type="image/png"), prompt],
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.0),
            )
            text = (resp.text or "").strip()
            if text:
                pool.report(key, None)
                return unnumber(text) if quote else text
            empties += 1
            try:
                last_fr = str(resp.candidates[0].finish_reason)
            except Exception:
                last_fr = ""
            if "RECITATION" in last_fr or attempt >= 3:
                quote = True
            if empties >= 10:
                with open(os.path.join(ROOT, "_ocr_review.txt"), "a", encoding="utf-8") as rv:
                    rv.write(f"{png_path}\t{last_fr}\n")
                return f"[page not extracted: model returned empty ({last_fr or 'unknown'}); listed in _ocr_review.txt]"
            pool.report(key, RuntimeError("empty response " + last_fr))
            classify_and_sleep(RuntimeError("empty"), attempt)
        except SystemExit:
            raise
        except Exception as e:
            s = str(e).lower()
            if "429" in s or "resource_exhausted" in s or "quota" in s:
                quota_hits += 1
                if quota_hits >= 2 * len(pool.keys):
                    raise SystemExit("Daily quota exhausted on all keys (429). Re-run after quota reset.")
            pool.report(key, e)
            if attempt == max_rounds:
                raise
            classify_and_sleep(e, attempt)
    raise RuntimeError(f"no response after {max_rounds} rounds (last finish_reason={last_fr})")


def render_pages(pdf_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    n = doc.page_count
    zoom = DPI / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    for i in range(n):
        out = os.path.join(out_dir, f"page_{i+1:04d}.png")
        if not os.path.exists(out):
            doc[i].get_pixmap(matrix=mat, alpha=False).save(out)
    return n


def process_file(pdf_path, pool, model, workers, force):
    base = os.path.basename(pdf_path)
    md_path = os.path.join(MD_DIR, os.path.splitext(base)[0] + ".md")
    if os.path.exists(md_path) and not force:
        return "skip-existing"
    cache_dir = os.path.join(CACHE, os.path.splitext(base)[0])
    n = render_pages(pdf_path, cache_dir)
    pngs = [os.path.join(cache_dir, f"page_{i+1:04d}.png") for i in range(n)]

    texts = {}
    todo = []
    for i, p in enumerate(pngs):
        c = p.replace(".png", ".md")
        cached = open(c, encoding="utf-8").read().strip() if os.path.exists(c) else ""
        if cached:
            texts[i] = cached
        else:
            todo.append((i, p))

    failed = []
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(transcribe_page, pool, model, p, i + 1, n, 4 * len(pool.keys)): i for i, p in todo}
            for fut in as_completed(futs):
                i = futs[fut]
                try:
                    t = fut.result()
                    texts[i] = t
                    open(pngs[i].replace(".png", ".md"), "w", encoding="utf-8").write(t)
                    print(f"  [{base}] page {i+1}/{n} ok", flush=True)
                except Exception as e:
                    failed.append((i, e))
                    print(f"  [{base}] page {i+1}/{n} FAILED: {e}", flush=True)
    if failed:
        return "failed"

    parts = []
    for i in range(n):
        parts.append(texts[i].strip() + f"\n\n*[Page {i+1} of {n}]*")
    md = f"# {os.path.splitext(base)[0]} — OCR transcription (Gemini)\n\n" + "\n\n---\n\n".join(parts) + "\n"
    os.makedirs(MD_DIR, exist_ok=True)
    open(md_path, "w", encoding="utf-8").write(md)
    shutil.rmtree(cache_dir, ignore_errors=True)
    return "converted"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="substring filter on pdf filename")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--pdf-dir", default=None, help="alternative input folder of PDFs")
    ap.add_argument("--md-dir", default=None, help="alternative output folder for md files")
    args = ap.parse_args()

    global PDF_DIR, MD_DIR
    if args.pdf_dir:
        PDF_DIR = args.pdf_dir if os.path.isabs(args.pdf_dir) else os.path.join(ROOT, args.pdf_dir)
    if args.md_dir:
        MD_DIR = args.md_dir if os.path.isabs(args.md_dir) else os.path.join(ROOT, args.md_dir)
    os.makedirs(MD_DIR, exist_ok=True)

    env = load_env()
    keys = collect_keys(env)
    if not keys:
        sys.exit("No Gemini API keys found. Put GEMINI_KEY_1..GEMINI_KEY_10 (or GEMINI_API_KEYS=k1,k2,...) in .env")
    print(f"[engine] {len(keys)} API keys loaded", flush=True)
    pool = KeyPool(keys)
    model = env.get("GEMINI_MODEL") or "gemini-3.5-flash-lite"
    print(f"[engine] model = {model} (pinned)", flush=True)

    manifest = os.path.join(ROOT, "_ocr_manifest.tsv")
    if os.path.exists(manifest) and not args.pdf_dir:
        rows = [l.rstrip("\n").split("\t") for l in open(manifest, encoding="utf-8")][1:]
    else:
        import hashlib
        from pypdf import PdfReader
        rows = []
        for f in sorted(os.listdir(PDF_DIR)):
            if not f.lower().endswith(".pdf"):
                continue
            p = os.path.join(PDF_DIR, f)
            h = hashlib.md5(open(p, "rb").read()).hexdigest()
            try:
                pg = len(PdfReader(p).pages)
            except Exception:
                pg = -1
            rows.append((h, str(pg), str(os.path.getsize(p)), f))
    by_hash = {}
    for h, pg, sz, f in rows:
        by_hash.setdefault(h, f)

    stats = {"converted": 0, "skip-existing": 0, "failed": 0, "dup-copied": 0}
    prog = open(PROGRESS, "a", encoding="utf-8")
    for h, pg, sz, f in rows:
        if args.only and args.only not in f:
            continue
        if f in SKIP and not args.force and not args.pdf_dir:
            print(f"[skip-roll] {f}", flush=True)
            continue
        pdf_path = os.path.join(PDF_DIR, f)
        md_name = os.path.splitext(f)[0] + ".md"
        md_path = os.path.join(MD_DIR, md_name)
        src = by_hash[h]
        if src != f:
            src_md = os.path.join(MD_DIR, os.path.splitext(src)[0] + ".md")
            if os.path.exists(src_md):
                if not os.path.exists(md_path):
                    shutil.copyfile(src_md, md_path)
                    stats["dup-copied"] += 1
                    print(f"[dup] {f} <- {src}", flush=True)
                continue
        print(f"[ocr] {f} ({pg} pages)", flush=True)
        t0 = time.time()
        try:
            st = process_file(pdf_path, pool, model, args.workers, args.force)
        except SystemExit:
            raise
        except Exception as e:
            print(f"[ocr] {f} ERROR: {e}", flush=True)
            st = "failed"
        stats[st] = stats.get(st, 0) + 1
        prog.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{st}\t{time.time()-t0:.0f}s\t{f}\n")
        prog.flush()
        print(f"[ocr] {f} -> {st} ({time.time()-t0:.0f}s)", flush=True)
    prog.close()
    print("[engine] done:", stats, flush=True)
    print("[engine] key usage:", {k[-4:]: v for k, v in pool.usage.items()}, flush=True)


if __name__ == "__main__":
    main()

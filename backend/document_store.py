"""Read-only access to the markdown corpus under source_documents/md.

Serves the READ SOURCE action in the Amendment Intelligence view, so a row in the
amendment ledger can be checked against the document it was extracted from.

Security model (ADR-0001): a request supplies a *basename only*, and that
basename is looked up in an allowlist built by walking the corpus. A path is
never constructed from user input, so there is no traversal surface to get wrong.

On Windows this matters considerably more than it looks. Starlette's {name}
convertor matches [^/]+, so a forward-slash traversal 404s at the router and
never arrives here -- but a backslash value and a drive-absolute value both reach
the handler completely intact, and pathlib then resolves them outside the corpus:

    CORPUS_ROOT / '..\\..\\backend\\ifsca_exam.db'  -> the real database, exists
    CORPUS_ROOT / 'C:\\Windows\\win.ini'            -> C:\\Windows\\win.ini, exists

The second is not a partial escape. pathlib discards the left operand entirely
when the right side carries a drive, so the corpus root stops being involved at
all. A NUL byte is a third, separate hazard: read_text() on one raises
ValueError, which would surface as a 500 rather than the uniform 404 this module
promises, and the 400/500 split would itself become an existence oracle.

Note also that the corpus files are not at the md root -- they sit in ten
numbered bucket subdirectories -- so the walk is required to find a legitimate
document at all, not merely to reject a malicious one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
CORPUS_ROOT = PROJECT_ROOT / "source_documents" / "md"

# basename -> absolute Path. Built once on first use, following the
# _INITIALIZED_DB_PATHS lazy-cache precedent at database.py:986.
# Trade-off, disclosed: a newly added .md file needs a server restart to appear.
_INDEX: dict[str, Path] | None = None


def _is_safe_basename(name: str) -> bool:
    """Reject anything that is not a plain filename before it is ever looked up.

    Defence in depth. The allowlist alone already defeats every form below,
    because none of them is a key in it. This explicit gate exists so the intent
    stays legible at the boundary and so a future refactor that starts joining
    user input to CORPUS_ROOT cannot silently become an arbitrary file read.
    """
    if not name or "\x00" in name:
        return False
    if not name.endswith(".md"):
        return False
    if "/" in name or "\\" in name:
        return False
    if name in (".", ".."):
        return False
    # A drive letter ("C:x.md") or a UNC prefix makes pathlib discard the left
    # operand of a join. Path.is_absolute() is unreliable for a bare drive on
    # some inputs, so check the shape directly.
    if len(name) >= 2 and name[1] == ":":
        return False
    return True


def _build_index() -> dict[str, Path]:
    if not CORPUS_ROOT.is_dir():
        return {}
    index: dict[str, Path] = {}
    for path in CORPUS_ROOT.rglob("*.md"):
        if not path.is_file():
            continue
        # 211 files across 10 buckets with zero basename collisions, so a
        # basename is a safe unique key. First match wins if that ever changes,
        # which keeps behaviour deterministic rather than walk-order dependent.
        index.setdefault(path.name, path)
    return index


def index() -> dict[str, Path]:
    """The cached basename -> absolute-path allowlist."""
    global _INDEX
    if _INDEX is None:
        _INDEX = _build_index()
    return _INDEX


def resolve(name: str) -> Path | None:
    """Absolute path for an allowlisted corpus basename, else None."""
    if not _is_safe_basename(name):
        return None
    path = index().get(name)
    if path is None:
        return None
    # Belt and braces: whatever the walk produced must still sit under the corpus
    # once symlinks are resolved. relative_to raises ValueError when it does not.
    try:
        resolved = path.resolve()
        resolved.relative_to(CORPUS_ROOT.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def read_document(name: str) -> dict[str, Any] | None:
    """Corpus document content, or None for anything not allowlisted.

    errors="replace" because these are OCR transcriptions of scanned PDFs; a
    stray undecodable byte must not turn a readable document into a 500.
    """
    path = resolve(name)
    if path is None:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return {
        "name": path.name,
        "bucket": path.parent.name,
        "lines": text.count("\n") + (0 if text.endswith("\n") else 1),
        "bytes": len(text.encode("utf-8")),
        "text": text,
    }

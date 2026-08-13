"""
In-memory cache for parsed PYQ questions.

Stores parsed questions so the submit endpoint can validate answers.
The cache lifetime must comfortably exceed the 60-minute PYQ exam timer;
previously 15 minutes, which expired mid-exam and rejected submissions.
"""

from __future__ import annotations

import time
from typing import Any

# Format: {pyq_id: {"questions": [ParsedQuestion...], "title": str, "timestamp": unix_time}}
_cache: dict[str, dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 2 * 60 * 60  # 2 hours


def cache_pyq_questions(pyq_id: str, questions: list[Any], title: str | None = None) -> None:
    """
    Store parsed questions in memory cache.

    Args:
        pyq_id: PYQ session identifier (e.g., "PYQ_doc_xxx")
        questions: List of ParsedQuestion objects
        title: Paper title, carried through to the submit endpoint for session records
    """
    _cache[pyq_id] = {
        "questions": questions,
        "title": title,
        "timestamp": time.time(),
    }


def get_pyq_questions(pyq_id: str) -> list[Any] | None:
    """
    Retrieve cached questions if they exist and haven't expired.

    Returns:
        List of ParsedQuestion objects or None if expired/not found
    """
    if pyq_id not in _cache:
        return None

    entry = _cache[pyq_id]
    age = time.time() - entry["timestamp"]

    if age > _CACHE_TTL_SECONDS:
        # Expired - remove and return None
        del _cache[pyq_id]
        return None

    return entry["questions"]


def get_pyq_title(pyq_id: str) -> str | None:
    """Return the cached paper title for a PYQ session, if present."""
    entry = _cache.get(pyq_id)
    if not entry:
        return None
    if time.time() - entry["timestamp"] > _CACHE_TTL_SECONDS:
        del _cache[pyq_id]
        return None
    return entry.get("title")


def clear_pyq_cache(pyq_id: str | None = None) -> None:
    """
    Clear cache entries. If pyq_id is None, clears all expired entries.

    Per Context7 docs: use dict.pop() for safe deletion.
    """
    if pyq_id:
        _cache.pop(pyq_id, None)
    else:
        # Clear all expired entries
        now = time.time()
        expired = [k for k, v in _cache.items() if now - v["timestamp"] > _CACHE_TTL_SECONDS]
        for k in expired:
            _cache.pop(k, None)

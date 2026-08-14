"""
In-memory cache for parsed PYQ questions.

Stores parsed questions temporarily (15 minutes) so submit endpoint can validate answers.

Per Context7 docs for Python: use dict with expiry timestamps for simple caching.
"""

from __future__ import annotations

import time
from typing import Any

# Format: {pyq_id: {"questions": [ParsedQuestion...], "timestamp": unix_time}}
_cache: dict[str, dict[str, Any]] = {}
# The PYQ exam timer is 60 minutes; a 15-minute cache TTL expired sessions
# mid-exam ("session expired, please reload"). 2h comfortably covers a full
# attempt plus review time.
_CACHE_TTL_SECONDS = 7200  # 2 hours


def cache_pyq_questions(pyq_id: str, questions: list[Any]) -> None:
    """
    Store parsed questions in memory cache.

    Args:
        pyq_id: PYQ session identifier (e.g., "PYQ_DOC1")
        questions: List of ParsedQuestion objects
    """
    _cache[pyq_id] = {
        "questions": questions,
        "timestamp": time.time()
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

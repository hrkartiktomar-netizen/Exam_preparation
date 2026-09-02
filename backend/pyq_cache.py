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


def cache_pyq_questions(
    pyq_id: str,
    questions: list[Any],
    marks_per_question: float | None = None,
    negative_marking_per_wrong: float | None = None,
) -> None:
    """
    Store parsed questions in memory cache.

    Args:
        pyq_id: PYQ session identifier (e.g., "PYQ_DOC1")
        questions: List of ParsedQuestion objects
        marks_per_question: Plan v6 2.3 - marks awarded per correct answer.
        negative_marking_per_wrong: Plan v6 2.3 - penalty per wrong answer (1/4 x marks).
    """
    _cache[pyq_id] = {
        "questions": questions,
        "timestamp": time.time(),
        "marks_per_question": marks_per_question,
        "negative_marking_per_wrong": negative_marking_per_wrong,
    }


def get_pyq_marking(pyq_id: str) -> dict[str, Any] | None:
    """
    Return the cached marking scheme for a session, or None if absent/expired.

    Plan v6 2.3: lets the submit endpoint score with the paper's actual marks
    and negative marking instead of hardcoded values.
    """
    if pyq_id not in _cache:
        return None
    entry = _cache[pyq_id]
    if time.time() - entry["timestamp"] > _CACHE_TTL_SECONDS:
        del _cache[pyq_id]
        return None
    if entry.get("marks_per_question") is None:
        return None
    return {
        "marks_per_question": entry["marks_per_question"],
        "negative_marking_per_wrong": entry["negative_marking_per_wrong"],
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

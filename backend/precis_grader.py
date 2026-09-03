"""Précis grading (plan v6 sub-phase 5.1).

Grades a Phase-II descriptive précis against the word limit, title requirement,
coverage of the model précis, and language quality. Scaled to the component's
marks (IFSCA 35, SEBI 30). Gemini-first with a deterministic local fallback so
the lab stays usable without API quota.
"""

from __future__ import annotations

import re
from typing import Any

from gemini_integration import call_json, gemini_available, _contract_prompt


PRECIS_SCHEMA = {
    "type": "object",
    "properties": {
        "word_limit_score": {"type": "number"},
        "title_score": {"type": "number"},
        "coverage_score": {"type": "number"},
        "language_score": {"type": "number"},
        "feedback": {"type": "string"},
    },
    "required": ["word_limit_score", "title_score", "coverage_score", "language_score", "feedback"],
}


def _count_words(text: str) -> int:
    return len([t for t in re.split(r"\s+", (text or "").strip()) if t])


def _extract_title(precis_text: str) -> str | None:
    """A précis title is a standalone leading line, often bold or Title-cased."""
    lines = [line.strip() for line in (precis_text or "").split("\n") if line.strip()]
    if not lines:
        return None
    first = lines[0]
    if len(first) <= 80 and len(first.split()) <= 12:
        return first.strip("*").strip()
    return None


def _local_coverage(user_text: str, model_precis: str) -> float:
    """Crude key-term overlap between the user précis and the model précis."""
    def terms(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-z]{4,}", (text or "").lower())}
    model_terms = terms(model_precis)
    if not model_terms:
        return 0.5
    user_terms = terms(user_text)
    overlap = len(model_terms & user_terms)
    return min(1.0, overlap / max(1, int(len(model_terms) * 0.4)))


def grade_precis(
    user_text: str,
    passage_text: str,
    model_precis: str,
    word_limit_min: int,
    word_limit_max: int,
    title_required: bool = True,
    max_marks: int = 35,
) -> dict[str, Any]:
    """Grade a précis and scale the result to `max_marks`.

    Returns a dict with `score`, `max_marks`, `feedback`, and a `components`
    breakdown (word_limit, title, coverage, language) each expressed as a 0-1
    fraction of its share of the marks.
    """
    word_count = _count_words(user_text)
    title = _extract_title(user_text)

    # Word-limit component: full inside the band, tapering outside (±5 tolerance).
    tol_min, tol_max = word_limit_min - 5, word_limit_max + 5
    if tol_min <= word_count <= tol_max:
        word_limit_frac = 1.0
    else:
        distance = (tol_min - word_count) if word_count < tol_min else (word_count - tol_max)
        word_limit_frac = max(0.0, 1.0 - distance / max(1, word_limit_max))

    title_frac = 1.0 if title else (0.0 if title_required else 0.5)

    if gemini_available() and model_precis:
        prompt = _contract_prompt(
            "precis_grading",
            "Grade a précis written for an IFSCA/SEBI descriptive paper.",
            f"""
Original passage:
{passage_text[:3000]}

Model précis (reference):
{model_precis[:1500]}

Candidate précis:
{user_text[:2000]}

Word limit: {word_limit_min}-{word_limit_max} words. Candidate wrote {word_count} words.
Title required: {title_required}. Candidate title: {title or '(none)'}

Score each of coverage and language from 0 to 1:
- coverage_score: how completely the candidate précis captures the passage's key points relative to the model précis.
- language_score: concision, clarity, grammar, and own-words expression.
Return JSON only.
""",
        )
        result = call_json(prompt, schema=PRECIS_SCHEMA, temperature=0.1, operation="precis_grading", profile="accuracy")
        if isinstance(result, dict):
            coverage = max(0.0, min(1.0, float(result.get("coverage_score", 0))))
            language = max(0.0, min(1.0, float(result.get("language_score", 0))))
            feedback = result.get("feedback", "")
            ai_model = "gemini"
        else:
            coverage = _local_coverage(user_text, model_precis)
            language = 0.6
            feedback = "Local fallback grading (Gemini unavailable)."
            ai_model = None
    else:
        coverage = _local_coverage(user_text, model_precis)
        language = 0.6 if word_count >= word_limit_min else 0.4
        feedback = "Local fallback grading (Gemini unavailable)."
        ai_model = None

    # Weighted split of the component marks: word limit 25%, title 15%, coverage 40%, language 25%.
    composite = (
        0.25 * word_limit_frac
        + 0.15 * title_frac
        + 0.40 * coverage
        + 0.25 * language
    )
    score = round(max(0.0, min(1.0, composite)) * max_marks, 2)

    return {
        "score": score,
        "max_marks": max_marks,
        "word_count": word_count,
        "title": title,
        "feedback": feedback,
        "ai_model": ai_model,
        "components": {
            "word_limit": round(word_limit_frac, 3),
            "title": round(title_frac, 3),
            "coverage": round(coverage, 3),
            "language": round(language, 3),
        },
    }

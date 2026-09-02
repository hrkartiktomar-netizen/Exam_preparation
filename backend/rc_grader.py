"""Reading-comprehension grading (plan v6 sub-phase 5.2).

Grades a candidate's own-words answers to a passage's sub-questions against the
model answers, penalising answers that copy the passage verbatim (>70% overlap).
Scaled to the component's marks (IFSCA 35, SEBI 40). Gemini-first with a
deterministic local fallback.
"""

from __future__ import annotations

import re
from typing import Any

from gemini_integration import call_json, gemini_available, _contract_prompt


RC_SCHEMA = {
    "type": "object",
    "properties": {
        "per_question": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "coverage": {"type": "number"},
                    "own_words": {"type": "boolean"},
                    "feedback": {"type": "string"},
                },
                "required": ["coverage", "own_words"],
            },
        },
        "overall_feedback": {"type": "string"},
    },
    "required": ["per_question", "overall_feedback"],
}


def _ngrams(text: str, n: int = 4) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    if len(words) < n:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def _overlap_fraction(answer: str, source: str) -> float:
    """Fraction of the answer's 4-grams found verbatim in the source passage."""
    answer_grams = _ngrams(answer)
    if not answer_grams:
        return 0.0
    source_grams = _ngrams(source)
    return len(answer_grams & source_grams) / len(answer_grams)


def _local_coverage(answer: str, model_answer: str) -> float:
    def terms(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-z]{4,}", (text or "").lower())}
    model_terms = terms(model_answer)
    if not model_terms:
        return 0.5
    return min(1.0, len(model_terms & terms(answer)) / max(1, int(len(model_terms) * 0.4)))


def grade_rc(
    answers: list[str],
    questions: list[str],
    model_answers: list[str],
    passage_text: str,
    max_marks: int = 35,
) -> dict[str, Any]:
    """Grade RC sub-answers and scale to `max_marks`.

    `answers`, `questions`, and `model_answers` are parallel lists (one entry per
    sub-question). Answers copying >70% of the passage (by 4-gram overlap) are
    penalised because the paper requires answers "in your own words".
    """
    n = min(len(answers), len(model_answers))
    per_question: list[dict[str, Any]] = []

    use_gemini = gemini_available() and n > 0
    gemini_result: dict[str, Any] | None = None
    if use_gemini:
        qa_block = "\n\n".join(
            f"Q{i + 1}: {questions[i] if i < len(questions) else ''}\n"
            f"Model answer: {model_answers[i][:400]}\n"
            f"Candidate answer: {answers[i][:500]}"
            for i in range(n)
        )
        prompt = _contract_prompt(
            "rc_grading",
            "Grade reading-comprehension answers written in the candidate's own words.",
            f"""
Passage:
{passage_text[:3000]}

For each sub-question below, score coverage from 0 to 1 against the model answer and
set own_words=false if the candidate answer largely copies the passage verbatim.
{qa_block}

Return JSON only.
""",
        )
        gemini_result = call_json(prompt, schema=RC_SCHEMA, temperature=0.1, operation="rc_grading", profile="accuracy")

    for i in range(n):
        overlap = _overlap_fraction(answers[i], passage_text)
        copied = overlap > 0.70
        if isinstance(gemini_result, dict) and i < len(gemini_result.get("per_question", [])):
            entry = gemini_result["per_question"][i]
            coverage = max(0.0, min(1.0, float(entry.get("coverage", 0))))
            own_words = bool(entry.get("own_words", True)) and not copied
            feedback = entry.get("feedback", "")
            ai_model = "gemini"
        else:
            coverage = _local_coverage(answers[i], model_answers[i])
            own_words = not copied
            feedback = "Copied too closely from the passage." if copied else ""
            ai_model = None
        # Penalise verbatim copying: answers must be in the candidate's own words.
        effective = coverage * (0.4 if copied else 1.0)
        per_question.append({
            "question_index": i + 1,
            "coverage": round(coverage, 3),
            "own_words": own_words,
            "overlap_fraction": round(overlap, 3),
            "effective": round(effective, 3),
            "feedback": feedback,
            "ai_model": ai_model,
        })

    if per_question:
        composite = sum(q["effective"] for q in per_question) / len(per_question)
    else:
        composite = 0.0
    score = round(max(0.0, min(1.0, composite)) * max_marks, 2)

    return {
        "score": score,
        "max_marks": max_marks,
        "questions_graded": len(per_question),
        "per_question": per_question,
        "overall_feedback": (gemini_result or {}).get("overall_feedback", "") if isinstance(gemini_result, dict) else "",
        "ai_model": "gemini" if (isinstance(gemini_result, dict) and per_question) else None,
    }

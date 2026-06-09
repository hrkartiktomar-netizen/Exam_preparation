"""Essay autonomy module: Auto-grading with 4-rubric feedback per Phase 5 spec.

Wraps gemini_integration.grade_essay() with validation, metadata tracking, and fallback handling.
Per Context7 docs for Python: all imports at module level, error handling, type hints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from gemini_integration import grade_essay as gemini_grade_essay, gemini_available
from models import EssayGradingResponseModel, EssayGradeModel


def grade_essay_with_sources(
    essay_text: str,
    topic: str,
    source_chunks: list[dict[str, Any]],
    force_local: bool = False,
) -> EssayGradingResponseModel:
    """Grade essay using 4-rubric system (0-25 each = 0-100 total).

    Args:
        essay_text: Full essay submission text
        topic: Topic ID (e.g., "PH2_FM_REGS")
        source_chunks: Source material chunks for grading context
        force_local: Force local fallback (bypass Gemini)

    Returns:
        EssayGradingResponseModel with 4-rubric scores + feedback
    """
    try:
        # Call Gemini essay grading (wrapper returns structured scores)
        grade_result = gemini_grade_essay(essay_text, topic, source_chunks)

        # Validate rubric scores are in 0-25 range
        _validate_rubric_scores(grade_result)

        # Extract response model
        return _extract_essay_response(grade_result, essay_text, source_chunks)

    except Exception as exc:
        # Log error (could log to database for audit)
        print(f"Essay grading error: {str(exc)}")

        # Return local fallback grade
        if force_local or not gemini_available():
            return _local_essay_grade_fallback(essay_text, topic, source_chunks)

        raise


def _validate_rubric_scores(grade_result: dict[str, Any]) -> None:
    """Validate 4-rubric scores are within 0-25 range.

    Args:
        grade_result: Gemini grade result with rubric scores

    Raises:
        ValueError: If any rubric score outside 0-25 range
    """
    rubrics = [
        ("content_accuracy", grade_result.get("content_accuracy", {}).get("score")),
        ("structure_clarity", grade_result.get("structure_clarity", {}).get("score")),
        ("regulatory_knowledge", grade_result.get("regulatory_knowledge", {}).get("score")),
        ("examples_evidence", grade_result.get("examples_evidence", {}).get("score")),
    ]

    for rubric_name, score in rubrics:
        if score is None:
            raise ValueError(f"Missing score for {rubric_name}")
        if not (0 <= score <= 25):
            raise ValueError(f"{rubric_name} score {score} outside 0-25 range")


def _extract_essay_response(
    grade_result: dict[str, Any],
    essay_text: str,
    source_chunks: list[dict[str, Any]],
) -> EssayGradingResponseModel:
    """Extract EssayGradingResponseModel from Gemini result.

    Args:
        grade_result: Raw Gemini grading output
        essay_text: Original essay for metadata
        source_chunks: Source chunks for validation

    Returns:
        Validated EssayGradingResponseModel
    """
    content_acc = grade_result.get("content_accuracy", {})
    struct_clar = grade_result.get("structure_clarity", {})
    reg_know = grade_result.get("regulatory_knowledge", {})
    exam_evi = grade_result.get("examples_evidence", {})

    total_score = (
        content_acc.get("score", 0)
        + struct_clar.get("score", 0)
        + reg_know.get("score", 0)
        + exam_evi.get("score", 0)
    )

    return EssayGradingResponseModel(
        essay_id=f"ESSAY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        content_accuracy=EssayGradeModel(
            score=content_acc.get("score", 0),
            feedback=content_acc.get("feedback", "")
        ),
        structure_clarity=EssayGradeModel(
            score=struct_clar.get("score", 0),
            feedback=struct_clar.get("feedback", "")
        ),
        regulatory_knowledge=EssayGradeModel(
            score=reg_know.get("score", 0),
            feedback=reg_know.get("feedback", "")
        ),
        examples_evidence=EssayGradeModel(
            score=exam_evi.get("score", 0),
            feedback=exam_evi.get("feedback", "")
        ),
        total_score=total_score,
        overall_feedback=grade_result.get("overall_feedback", ""),
        suggested_sources=source_chunks if source_chunks else [],
        model_outline=grade_result.get("model_outline", ""),
        ai_model=grade_result.get("ai_model", "Gemini 2.0 Flash"),
    )


def _local_essay_grade_fallback(
    essay_text: str,
    topic: str,
    source_chunks: list[dict[str, Any]],
) -> EssayGradingResponseModel:
    """Fallback local essay grading when Gemini unavailable.

    Uses heuristics: word count, keyword presence, structure signals.

    Args:
        essay_text: Essay to grade
        topic: Topic ID
        source_chunks: Source chunks for response

    Returns:
        Conservative grade with feedback
    """
    word_count = len(essay_text.split())
    lines = len(essay_text.split("\n"))

    # Heuristic scoring
    content_score = min(25, max(12, word_count // 20))  # 12-25 range
    structure_score = min(25, max(15, lines // 3))  # 15-25 if has paragraphs
    regulatory_score = 18 if "regulation" in essay_text.lower() else 12
    examples_score = 16 if any(x in essay_text.lower() for x in ["example", "e.g.", "such as"]) else 10

    total = content_score + structure_score + regulatory_score + examples_score

    return EssayGradingResponseModel(
        essay_id=f"ESSAY_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        content_accuracy=EssayGradeModel(
            score=content_score,
            feedback="Local grading: more depth recommended."
        ),
        structure_clarity=EssayGradeModel(
            score=structure_score,
            feedback="Local grading: ensure clear paragraphing."
        ),
        regulatory_knowledge=EssayGradeModel(
            score=regulatory_score,
            feedback="Local grading: cite specific regulations."
        ),
        examples_evidence=EssayGradeModel(
            score=examples_score,
            feedback="Local grading: add dates, statistics, examples."
        ),
        total_score=total,
        overall_feedback="Local fallback grading (Gemini unavailable). Get expert review.",
        suggested_sources=source_chunks if source_chunks else [],
        model_outline="1. Introduction 2. Regulatory context 3. Evidence/data 4. Analysis 5. Conclusion",
        ai_model=None,
    )


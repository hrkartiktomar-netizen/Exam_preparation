"""Law revision engine: Daily autonomous law study planning with spaced review.

Orchestrates: high-yield provisions, recent amendments, weak areas, spaced review scheduling.
Per Context7 docs for Python: all imports at module level, error handling, type hints.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import database as db
from gemini_integration import generate_law_revision_plan, gemini_available
from models import (
    LawRevisionModel,
    HighYieldProvisionModel,
    RecentAmendmentModel,
    WeakLegalAreaModel,
    SpacedReviewItemModel,
)


def daily_law_revision(
    user_id: str = "default",
    days_back: int = 30,
    lines_per_day: int = 80,
    force_local: bool = False,
) -> LawRevisionModel:
    """Generate daily law revision plan: high-yield, amendments, weak areas, spaced review.

    Args:
        user_id: User ID (currently not differentiated)
        days_back: Look back N days for recent amendments
        force_local: Force local plan without Gemini

    Returns:
        LawRevisionModel with provisions, amendments, weak areas, due reviews
    """
    try:
        # 1. Fetch high-yield provisions (amendments + frequent topics)
        provisions = db.get_high_yield_provisions(limit=15)
        high_yield = [
            HighYieldProvisionModel.model_validate(p)
            for p in provisions
        ]

        # 2. Fetch recent amendments
        amendments = db.get_recent_amendments(days_back=days_back, limit=20)
        recent_amend = [
            RecentAmendmentModel.model_validate(a)
            for a in amendments
        ]

        # 3. Fetch weak legal areas (accuracy < 60%)
        weak_areas = db.get_weak_legal_areas(limit=10)
        weak_legal = [
            WeakLegalAreaModel.model_validate(w)
            for w in weak_areas
        ]

        # 4. Fetch spaced review due items
        due_items = db.get_law_review_due(limit=20)
        spaced_due = [
            SpacedReviewItemModel.model_validate(item)
            for item in due_items
        ]

        # 5. Generate daily Act slice and AI revision focus.
        act_slice = db.daily_ifsca_act_revision(lines_per_day=lines_per_day)
        ai_plan = None
        if not force_local and gemini_available():
            ai_plan = generate_law_revision_plan(act_slice, force_local=False)
        else:
            ai_plan = generate_law_revision_plan(act_slice, force_local=True)

        return LawRevisionModel(
            title=act_slice.get("title"),
            document=act_slice.get("document"),
            line_start=act_slice.get("line_start"),
            line_end=act_slice.get("line_end"),
            daily_text=act_slice.get("daily_text"),
            full_text=act_slice.get("full_text"),
            total_lines=act_slice.get("total_lines"),
            day_index=act_slice.get("day_index"),
            total_days=act_slice.get("total_days"),
            ai_revision=ai_plan,
            high_yield_provisions=high_yield,
            recent_amendments=recent_amend,
            weak_legal_areas=weak_legal,
            spaced_review_due=spaced_due,
            ai_revision_focus=ai_plan.get("revision_focus") if ai_plan else None,
        )

    except Exception as exc:
        print(f"Law revision generation error: {str(exc)}")
        # Fallback: return empty but valid model
        return LawRevisionModel()


def schedule_essay_provisions_for_review(essay_id: str, topic_id: str) -> list[str]:
    """Schedule law provisions from essay for spaced review (SM-2).

    After user writes/grades an essay, relevant provisions are scheduled for
    periodic review using spaced repetition intervals.

    Args:
        essay_id: ID of completed essay
        topic_id: Topic of essay (e.g., "PH2_FM_REGS")

    Returns:
        List of scheduled review IDs
    """
    scheduled_ids = []

    try:
        # Get high-yield provisions for this topic
        provisions = db.get_high_yield_provisions(limit=5)
        filtered = [p for p in provisions if p.get("topic_id") == topic_id]

        # Schedule for SM-2 intervals (1, 3, 7, 14, 30 days)
        for provision in filtered:
            review_id = db.schedule_law_review(
                item_type="provision",
                item_id=provision.get("item_id", ""),
                topic_id=topic_id,
                essay_id=essay_id,
                interval_days=1,  # Start at 1 day
            )
            scheduled_ids.append(review_id)

        return scheduled_ids

    except Exception as exc:
        print(f"Error scheduling essay provisions: {str(exc)}")
        return []


def mark_review_complete(review_id: str, success: bool = True) -> dict[str, Any]:
    """Mark a law review item as complete and update SM-2 scheduling.

    Updates ease factor and next due date per SM-2 algorithm:
    - Success: increase ease, longer interval
    - Failure: decrease ease, retry sooner

    Args:
        review_id: Review item ID
        success: Whether user successfully completed review

    Returns:
        Update status with new ease and interval
    """
    try:
        result = db.mark_law_review_complete(review_id, success=success)
        return result
    except ValueError as exc:
        return {"error": str(exc), "review_id": review_id}
    except Exception as exc:
        print(f"Error marking review complete: {str(exc)}")
        return {"error": str(exc), "review_id": review_id}


def get_spaced_review_due(limit: int = 20) -> list[SpacedReviewItemModel]:
    """Get law review items due today for spaced revision.

    Returns:
        List of due review items sorted by due date and ease
    """
    try:
        due_items = db.get_law_review_due(limit=limit)
        return [
            SpacedReviewItemModel.model_validate(item)
            for item in due_items
        ]
    except Exception as exc:
        print(f"Error fetching due reviews: {str(exc)}")
        return []


def get_weak_legal_areas(limit: int = 10) -> list[WeakLegalAreaModel]:
    """Get legal areas where user's accuracy is weak (<60%).

    These topics should get priority in daily revision.

    Args:
        limit: Maximum topics to return

    Returns:
        List of weak legal areas sorted by accuracy (lowest first)
    """
    try:
        weak = db.get_weak_legal_areas(limit=limit)
        return [
            WeakLegalAreaModel.model_validate(w)
            for w in weak
        ]
    except Exception as exc:
        print(f"Error fetching weak areas: {str(exc)}")
        return []


def get_recent_amendments(days_back: int = 30, limit: int = 20) -> list[RecentAmendmentModel]:
    """Get recent amendments from past N days (highest priority study material).

    Args:
        days_back: Look back N days
        limit: Maximum amendments to return

    Returns:
        List of recent amendments sorted by exam relevance
    """
    try:
        amendments = db.get_recent_amendments(days_back=days_back, limit=limit)
        return [
            RecentAmendmentModel.model_validate(a)
            for a in amendments
        ]
    except Exception as exc:
        print(f"Error fetching recent amendments: {str(exc)}")
        return []


def get_high_yield_provisions(limit: int = 15) -> list[HighYieldProvisionModel]:
    """Get high-yield provisions most likely to appear in exam.

    Args:
        limit: Maximum provisions to return

    Returns:
        List of high-yield provisions sorted by examrelevance
    """
    try:
        provisions = db.get_high_yield_provisions(limit=limit)
        return [
            HighYieldProvisionModel.model_validate(p)
            for p in provisions
        ]
    except Exception as exc:
        print(f"Error fetching high-yield provisions: {str(exc)}")
        return []

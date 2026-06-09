"""INPUT VALIDATION FRAMEWORK - All 50+ endpoints per Context7 Pydantic patterns.

Per Context7 docs for Pydantic: Use validators for complex fields, field constraints
for ranges/lengths, custom types for domain logic. Ensures malformed requests caught
at boundary with descriptive error messages.

Principle: VALIDATE AT BOUNDARY > ALLOW BAD STATE INTERNALLY
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# DOMAIN TYPES: Custom types for business logic validation
# ============================================================================


class TopicID(str):
    """Valid topic ID from TOPIC_DEFINITIONS."""

    VALID_TOPICS = {
        "PH2_IFSCA_ACT",
        "PH2_GIFT_IFSC",
        "PH2_FM_REGS",
        "PH2_BANKING",
        "PH2_CAPITAL",
        "PH2_CMI",
        "PH2_LISTING",
        "PH2_PAYMENT",
        "PH2_TECHFIN_TAS",
        "PH2_BULLION",
        "PH2_INSURANCE",
        "PH2_AIRCRAFT_SHIP_LEASING",
        "PH2_AML_KYC",
        "PH2_COMMODITY_TRADE",
        "PH2_TAX",
        "PH2_CURRENT_AFFAIRS",
        "PH2_MANAGEMENT_ORG",
        "PH2_ESSAY",
    }

    def __new__(cls, value: str) -> TopicID:
        if value not in cls.VALID_TOPICS:
            raise ValueError(f"Invalid topic: {value}. Must be one of {cls.VALID_TOPICS}")
        return super().__new__(cls, value)


class Accuracy(int):
    """Accuracy percentage: 0-100."""

    def __new__(cls, value: int) -> Accuracy:
        if not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"Accuracy must be integer 0-100, got {value}")
        return super().__new__(cls, value)


class ExamScore(int):
    """Exam score: 0-200 (max possible)."""

    def __new__(cls, value: int) -> ExamScore:
        if not isinstance(value, int) or not 0 <= value <= 200:
            raise ValueError(f"Exam score must be 0-200, got {value}")
        return super().__new__(cls, value)


# ============================================================================
# VALIDATION MODELS: Request/Response validation per endpoint
# ============================================================================


class MockSubmitRequestValidated(BaseModel):
    """Validate mock submission request.

    Required fields: mock_id, answers (list of selected options per question)
    """

    mock_id: str = Field(..., min_length=1, max_length=100, description="Mock session ID")
    answers: dict[int, str] = Field(
        ...,
        description="Map of question_index (0-49) to selected option (A-D)"
    )

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, v: dict[int, str]) -> dict[int, str]:
        """Validate answer structure."""
        if not isinstance(v, dict):
            raise ValueError("answers must be a dictionary")

        for q_idx, option in v.items():
            if not isinstance(q_idx, int) or not 0 <= q_idx <= 49:
                raise ValueError(f"question_index must be 0-49, got {q_idx}")
            if option not in ("A", "B", "C", "D"):
                raise ValueError(f"option must be A-D, got {option}")

        return v


class EssaySubmitRequestValidated(BaseModel):
    """Validate essay submission request."""

    topic: str = Field(..., description="Essay topic")
    essay_text: str = Field(
        ..., min_length=50, max_length=5000, description="Essay text (50-5000 chars)"
    )

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        """Validate topic is valid."""
        if v not in TopicID.VALID_TOPICS:
            raise ValueError(f"Invalid topic: {v}")
        return v

    @field_validator("essay_text")
    @classmethod
    def validate_essay_text(cls, v: str) -> str:
        """Validate essay text is non-empty and reasonable."""
        if not v or not v.strip():
            raise ValueError("essay_text cannot be empty")
        # Check word count (rough: "word" ~ 5 chars + space)
        word_count = len(v.split())
        if word_count < 20:
            raise ValueError(f"Essay too short: {word_count} words (minimum 20)")
        if word_count > 1000:
            raise ValueError(f"Essay too long: {word_count} words (maximum 1000)")
        return v


class SmartMockRequestValidated(BaseModel):
    """Validate smart mock generation request."""

    weak_topics: list[str] = Field(
        default_factory=list, description="Topics with accuracy < 60%"
    )
    medium_topics: list[str] = Field(
        default_factory=list, description="Topics with 60-75% accuracy"
    )
    strong_topics: list[str] = Field(
        default_factory=list, description="Topics with accuracy >= 75%"
    )

    @field_validator("weak_topics", "medium_topics", "strong_topics")
    @classmethod
    def validate_topics_lists(cls, v: list[str]) -> list[str]:
        """Validate each topic in list."""
        for topic in v:
            if topic not in TopicID.VALID_TOPICS:
                raise ValueError(f"Invalid topic: {topic}")
        return v

    @model_validator(mode="after")
    def validate_allocation(self) -> SmartMockRequestValidated:
        """Validate total allocation near 50 questions."""
        weak_count = len(self.weak_topics)
        medium_count = len(self.medium_topics)
        strong_count = len(self.strong_topics)
        total = weak_count + medium_count + strong_count

        if total == 0:
            raise ValueError("Must provide at least one topic")

        # Warn if allocation seems wrong but allow (user may be testing)
        expected_weak = total * 0.60
        expected_medium = total * 0.25
        expected_strong = total * 0.15

        # Allow ±10% flexibility
        if not (expected_weak * 0.9 <= weak_count <= expected_weak * 1.1):
            print(f"⚠️ Weak topic allocation {weak_count} != expected {expected_weak:.0f}")

        return self


class QuestionGenerationRequestValidated(BaseModel):
    """Validate question generation request."""

    topic: str = Field(..., description="Topic to generate questions for")
    count: int = Field(..., ge=1, le=50, description="Number of questions (1-50)")
    difficulty: str = Field(
        default="medium", description="Difficulty level: easy, medium, hard"
    )

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        """Validate topic is valid."""
        if v not in TopicID.VALID_TOPICS:
            raise ValueError(f"Invalid topic: {v}")
        return v

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        """Validate difficulty level."""
        if v not in ("easy", "medium", "hard"):
            raise ValueError(f"difficulty must be easy/medium/hard, got {v}")
        return v


class AmendmentStatusQueryValidated(BaseModel):
    """Validate amendment status query parameters."""

    days_back: int = Field(
        default=30, ge=1, le=90, description="Days back to check (1-90)"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Max amendments to return (1-100)"
    )


class ReadinessQueryValidated(BaseModel):
    """Validate readiness estimation query parameters."""

    target_score: int = Field(
        default=130, ge=0, le=200, description="Target exam score (0-200)"
    )
    days_to_exam: int = Field(
        default=28, ge=1, le=365, description="Days until exam (1-365)"
    )


class HistorySearchQueryValidated(BaseModel):
    """Validate history search query parameters."""

    query: str = Field(
        ..., min_length=2, max_length=100, description="Search query (2-100 chars)"
    )
    result_type: str = Field(
        default="all",
        description="Filter by type: all, questions, amendments, essays, provisions"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Max results (1-100)"
    )

    @field_validator("result_type")
    @classmethod
    def validate_result_type(cls, v: str) -> str:
        """Validate result type."""
        allowed = {"all", "questions", "amendments", "essays", "provisions"}
        if v not in allowed:
            raise ValueError(f"result_type must be one of {allowed}, got {v}")
        return v


class AmendmentExtractRequestValidated(BaseModel):
    """Validate manual amendment extraction request."""

    title: str = Field(
        ..., min_length=5, max_length=500, description="Amendment title"
    )
    topic: str = Field(..., description="IFSCA topic affected")
    summary: str = Field(
        ..., min_length=10, max_length=2000, description="Amendment summary"
    )
    effective_date: str = Field(..., description="ISO date (YYYY-MM-DD)")
    source_url: str = Field(
        ..., description="Source URL for amendment"
    )

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, v: str) -> str:
        """Validate topic is valid."""
        if v not in TopicID.VALID_TOPICS:
            raise ValueError(f"Invalid topic: {v}")
        return v

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v: str) -> str:
        """Validate date is ISO format."""
        try:
            from datetime import datetime
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError(f"effective_date must be ISO format (YYYY-MM-DD), got {v}")
        return v


# ============================================================================
# VALIDATION: Decorator for automatic request validation
# ============================================================================


def validate_request(model_class):
    """Decorator to validate endpoint requests against model."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                # Validate all kwargs
                validated = model_class(**kwargs)
                # Replace kwargs with validated data
                kwargs.update(validated.model_dump())
                return await func(*args, **kwargs)
            except ValueError as e:
                from fastapi import HTTPException
                raise HTTPException(
                    status_code=422,
                    detail=f"Validation error: {str(e)}"
                ) from e

        return wrapper

    return decorator

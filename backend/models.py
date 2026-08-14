"""API models for the IFSCA exam preparation system."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator


Difficulty = Literal["easy", "medium", "hard"]
TopicStatus = Literal["UNKNOWN", "CRITICAL", "WEAK", "MEDIUM", "STRONG"]


class OptionModel(BaseModel):
    label: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1)


class QuestionModel(BaseModel):
    question_id: str
    topic: str
    question_text: str = Field(min_length=1)
    options: list[OptionModel] = Field(min_length=4, max_length=4)
    correct_option: Literal["A", "B", "C", "D"]
    explanation: str = Field(min_length=1)
    source: str | None = None
    source_document_id: str | None = None
    source_chunk_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    citation_note: str | None = None
    is_amendment_based: bool = False
    difficulty: Difficulty = "medium"
    recency_score: int = Field(default=0, ge=0, le=100)
    created_by: str | None = None
    quality_score: float | None = None
    tested_fact: str | None = None
    trap_logic: str | None = None
    source_policy: str | None = None


class AttemptModel(BaseModel):
    id: int | str
    topic: str
    question_text: str = ""
    correct_option: Literal["A", "B", "C", "D"]
    your_option: str | None = None
    is_correct: bool
    time_spent_seconds: int = Field(default=0, ge=0)


class MockUploadModel(BaseModel):
    mock_id: str
    date: str
    phase: str = "phase_2"
    paper: str = "paper_2"
    questions: list[AttemptModel]
    source: str = "QRE"


class TopicModel(BaseModel):
    topic_id: str
    parent_topic_id: str | None = None
    # phase/paper are NULL for topics seeded from TOPIC_DEFINITIONS (the seed rows do not
    # carry these fields), so they must be optional or /api/topics 422s on a fresh database.
    phase: str | None = None
    paper: str | None = None
    display_name: str
    description: str
    base_weight: float
    exam_priority: int
    is_amendment_sensitive: bool


class TopicStatsModel(BaseModel):
    topic: str
    display_name: str | None = None
    total_seen: int = 0
    total_correct: int = 0
    accuracy_pct: float = 0.0
    status: TopicStatus = "UNKNOWN"
    last_tested: str | None = None
    weakness_score: float = 0.0
    recent_accuracy: float | None = None
    trend: str = "UNKNOWN"
    tier: int | None = None


class WeakTopicsResponseModel(BaseModel):
    weak_topics: list[TopicStatsModel]
    penalty_drill_needed: bool
    recommended_topic: str | None = None


class DocumentModel(BaseModel):
    document_id: str
    title: str
    category: str
    source_type: str
    source_url: str | None = None
    local_pdf_path: str | None = None
    local_text_path: str | None = None
    sha256: str | None = None
    pages: int = 0
    line_count: int = 0
    publication_date: str | None = None
    downloaded_at: str | None = None
    ingested_at: str | None = None
    status: str = "indexed"
    notes: str | None = None


class SourceChunkModel(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    category: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    topic_tags: list[str] = []
    excerpt: str
    rank: float | None = None
    authority_score: float | None = None
    exam_signal_score: float | None = None
    exam_source_score: float | None = None


class SourceSearchResponseModel(BaseModel):
    query: str
    topic_id: str | None = None
    total: int
    results: list[SourceChunkModel]


class IngestResponseModel(BaseModel):
    status: str
    documents_seen: int
    documents_indexed: int
    chunks_indexed: int
    skipped_existing: int
    errors: list[str] = []


class IngestionStatusModel(BaseModel):
    documents: int
    chunks: int
    fts_rows: int
    topics: int
    chunk_topic_links: int
    questions: int
    amendments: int


class PenaltyDrillRequestModel(BaseModel):
    topic: str
    current_accuracy: float = Field(default=0.0, ge=0, le=100)
    question_count: int = Field(default=10, ge=1, le=50)
    difficulty: Difficulty = "medium"
    drill_type: str = "weakness"


class PenaltyDrillResponseModel(BaseModel):
    drill_id: str
    topic: str
    questions: list[QuestionModel]
    time_limit_minutes: int = 15
    source_grounded: bool


class EssaySubmissionModel(BaseModel):
    prompt: str = "General IFSCA essay"
    essay_text: str = Field(min_length=100)
    topic: str = "PH2_ESSAY"
    time_limit_minutes: int | None = None


class EssayGradeModel(BaseModel):
    score: int = Field(ge=0, le=25)
    feedback: str


class EssayGradingResponseModel(BaseModel):
    essay_id: str | None = None
    content_accuracy: EssayGradeModel
    structure_clarity: EssayGradeModel
    regulatory_knowledge: EssayGradeModel
    examples_evidence: EssayGradeModel
    total_score: int = Field(ge=0, le=100)
    overall_feedback: str
    suggested_sources: list[SourceChunkModel] = []
    model_outline: str | None = None
    ai_model: str | None = None

    @model_validator(mode="after")
    def validate_total(self) -> "EssayGradingResponseModel":
        expected = (
            self.content_accuracy.score
            + self.structure_clarity.score
            + self.regulatory_knowledge.score
            + self.examples_evidence.score
        )
        if self.total_score != expected:
            self.total_score = expected
        return self


class AmendmentModel(BaseModel):
    amendment_id: str
    topic: str
    rule_name: str
    effective_date: str
    old_value: str | None = None
    new_value: str | None = None
    source_url: str = "manual"
    source_document_id: str | None = None
    source_chunk_id: str | None = None
    verify_status: str = "UNVERIFIED"
    priority: Literal["CRITICAL", "HIGH", "NORMAL", "LOW"] = "NORMAL"
    questions_needed: int = Field(default=3, ge=0, le=20)


class AmendmentResponseModel(BaseModel):
    status: str
    amendment_id: str
    questions_generated: int


class AmendmentExtractRequestModel(BaseModel):
    amendment_text: str = Field(min_length=20)
    amendment_url: str = "manual"
    save: bool = False


class SmartMockRequestModel(BaseModel):
    total_questions: int = Field(default=50, ge=5, le=100)
    mode: Literal["balanced", "weakness-heavy", "amendment-heavy", "pyq-like"] = "balanced"
    use_gemini: bool = True


class StudySessionRequestModel(BaseModel):
    minutes: int = Field(default=90, ge=15, le=240)
    focus: str | None = Field(default=None, max_length=500)


class SmartMockResponseModel(BaseModel):
    status: str
    mock_id: str
    total_questions: int
    allocation: dict[str, int]
    allocation_summary: dict[str, Any]
    weakness_analysis: list[TopicStatsModel]
    questions: list[QuestionModel]
    source_grounded: bool
    message: str
    time_limit_minutes: int = 60
    marks_per_question: float = 2.0
    negative_marking_per_wrong: float = 0.5
    exam_rules: dict[str, Any] = {}


class AnswerModel(BaseModel):
    question_id: str
    selected_answer: Literal["A", "B", "C", "D"] | None = Field(
        default=None,
        validation_alias=AliasChoices("selected_answer", "selected_option"),
    )
    time_spent_seconds: int = Field(
        default=0,
        ge=0,
        validation_alias=AliasChoices("time_spent_seconds", "time_taken_seconds"),
    )
    marked_for_review: bool = False


class MockSubmitRequestModel(BaseModel):
    answers: list[AnswerModel]


class MockSubmitResponseModel(BaseModel):
    mock_id: str
    total_questions: int
    total_answered: int
    total_correct: int
    total_wrong: int = 0
    total_unanswered: int = 0
    accuracy_pct: float
    raw_score: float = 0.0
    negative_marks: float = 0.0
    final_score: float = 0.0
    topic_breakdown: list[TopicStatsModel]
    question_analysis: list[dict[str, Any]] = []


class DashboardStatsModel(BaseModel):
    status: str = "ok"
    total_mocks_completed: int = 0
    smart_mocks_generated: int = 0
    total_questions_attempted: int = 0
    overall_accuracy: float = 0.0
    estimated_score: float = 0.0
    confidence_band: str = "low confidence until more attempts are recorded"
    weak_topics: list[TopicStatsModel] = []
    topic_heatmap: list[TopicStatsModel] = []
    recent_amendments: list[dict[str, Any]] = []
    ingestion: IngestionStatusModel
    next_recommended_action: str
    resource_health: dict[str, Any] = {}
    ai_status: dict[str, Any] = {}
    focus_plan: dict[str, Any] | None = None
    amendment_watchlist: list[dict[str, Any]] = []
    intelligence: dict[str, Any] = {}
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class HealthResponseModel(BaseModel):
    status: str
    api_keys_loaded: int
    gemini_available: bool
    central_ai_ready: bool = False
    gemini: dict[str, Any] = {}
    database_initialized: bool
    ingestion: IngestionStatusModel | None = None
    timestamp: str


class EssayPromptModel(BaseModel):
    prompt_id: str
    topic: str
    prompt: str


class QuestionGenerationRequestModel(BaseModel):
    topic: str
    count: int = Field(default=5, ge=1, le=50)
    difficulty: Difficulty = "medium"
    query: str | None = None

    @field_validator("topic")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        return value.strip().upper()


class ExamAnalyticsModel(BaseModel):
    """Topic-level analytics from a single exam."""
    topic_id: str
    accuracy_pct: float = Field(ge=0, le=100)
    time_spent_seconds: int = Field(ge=0)
    difficulty_rating: Difficulty = "medium"
    comparison_to_avg: float = 0.0


class ExamAnalyticsResponseModel(BaseModel):
    """Post-exam analytics breakdown by topic."""
    exam_id: str
    total_topics_analyzed: int
    overall_accuracy: float = Field(ge=0, le=100)
    topic_analytics: list[ExamAnalyticsModel]
    weak_topics: list[str] = []
    improvement_areas: list[str] = []
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AnalyticsTimelineModel(BaseModel):
    """Score progression across all mocks (trending)."""
    exam_id: str = Field(validation_alias=AliasChoices("exam_id", "mock_id"))
    score: float | None = None
    accuracy: float | None = None
    avg_topic_accuracy: float | None = Field(default=None, validation_alias=AliasChoices("avg_topic_accuracy", "avg_topic_acc"))
    topics_analyzed: int = 0
    created_at: str


class SRSTopicModel(BaseModel):
    """Spaced Repetition System topic review item."""
    review_id: str
    topic_id: str
    display_name: str | None = None
    due_at: str
    interval_days: int
    ease: float = Field(default=2.5, ge=1.3, le=4.0)
    last_result: str | None = None


class SRSScheduleRequestModel(BaseModel):
    """Request to schedule a topic for SRS review."""
    topic_id: str
    interval_days: int = Field(default=1, ge=1, le=30)


class StudyPathWeekModel(BaseModel):
    """Single week in a 12-week study path."""
    week: int = Field(ge=1, le=12)
    focus_topics: list[str] = Field(min_length=1, max_length=5)
    daily_questions: int = Field(ge=5, le=100)
    milestone: str
    status: str = "not_started"


class StudyPathModel(BaseModel):
    """Personalized 12-week exam preparation study path."""
    path_id: str
    exam_date: str
    weeks: list[StudyPathWeekModel]
    milestone_count: int = 12
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class StudyPathProgressModel(BaseModel):
    """Progress tracking for a study path week."""
    progress_id: str
    path_id: str
    week_number: int = Field(ge=1, le=12)
    completed_topics: list[str] = []
    score_history: list[float] = []
    status: str = "not_started"
    completed_at: str | None = None


# ============================================================================
# PHASE 5: Essay Autonomy & Law Revision Models
# ============================================================================

class SpacedReviewItemModel(BaseModel):
    """Spaced repetition review item (provision, amendment, regulation)."""
    review_id: str
    item_type: str  # "provision_amendment", "provision_regulation", etc.
    item_id: str
    topic_id: str
    due_at: str
    interval_days: int = Field(default=1, ge=1)
    ease: float = Field(default=2.5, ge=1.3, le=4.0)
    last_result: str | None = None  # "success", "failure", "skipped"
    display_name: str | None = None


class HighYieldProvisionModel(BaseModel):
    """High-yield provision from amendments (exam-relevant)."""
    item_id: str
    item_type: str
    topic_id: str
    title: str
    effective_date: str | None = None
    source_url: str | None = None
    priority: str | None = None
    questions_needed: int | None = None


class WeakLegalAreaModel(BaseModel):
    """Legal area where user's accuracy is weak (<60%)."""
    topic: str
    display_name: str | None = None
    total_seen: int
    total_correct: int
    accuracy_pct: float
    status: str | None = None
    last_tested: str | None = None


class RecentAmendmentModel(BaseModel):
    """Recent amendment for law revision."""
    amendment_id: str
    topic: str
    rule_name: str
    effective_date: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    source_url: str | None = None
    priority: str | None = None
    questions_needed: int | None = None
    created_at: str | None = None


class LawRevisionModel(BaseModel):
    """Daily law revision plan combining provisions, amendments, and spaced review."""
    title: str | None = None
    document: dict[str, Any] | None = None
    line_start: int | None = None
    line_end: int | None = None
    daily_text: str | None = None
    full_text: str | None = None
    total_lines: int | None = None
    day_index: int | None = None
    total_days: int | None = None
    ai_revision: dict[str, Any] | None = None
    high_yield_provisions: list[HighYieldProvisionModel] = []
    recent_amendments: list[RecentAmendmentModel] = []
    weak_legal_areas: list[WeakLegalAreaModel] = []
    spaced_review_due: list[SpacedReviewItemModel] = []
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    ai_revision_focus: str | None = None


class EssayReviewItemModel(BaseModel):
    """Essay-linked review item with spaced scheduling."""
    review_id: str
    essay_id: str
    item_type: str
    item_id: str
    topic_id: str
    due_at: str
    interval_days: int
    ease: float = Field(ge=1.3, le=4.0)
    referenced_text: str | None = None

-- ================================================================
-- MIGRATION: 005_knowledge_layer.sql
-- PURPOSE: Compiled-knowledge runtime (plan v6 Phase 1).
--          Facts, PYQ/descriptive stores, templates, fulltext store.
-- NOTE: previous_year_questions rebuild (CHECK constraint change for
--       option E) is handled in database._migrate_pyq_table_v2 (Python),
--       mirroring the _repair_pyq_schema pattern.
-- ================================================================

CREATE TABLE IF NOT EXISTS facts (
    fact_id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    module TEXT,
    statement TEXT NOT NULL,
    detail TEXT,
    numbers_json TEXT,
    effective_date TEXT,
    authority TEXT NOT NULL,
    yield TEXT NOT NULL,
    source_doc TEXT NOT NULL,
    source_page INTEGER,
    source_ref TEXT,
    tags_json TEXT
);

CREATE TABLE IF NOT EXISTS fact_topics (
    fact_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    PRIMARY KEY (fact_id, topic_id)
);

CREATE TABLE IF NOT EXISTS fact_subjects (
    fact_id TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    PRIMARY KEY (fact_id, subject_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS fact_fts USING fts5(
    fact_id UNINDEXED,
    statement,
    detail,
    tags
);

CREATE TABLE IF NOT EXISTS document_fulltext (
    document_id TEXT PRIMARY KEY,
    title TEXT,
    source_doc TEXT,
    line_count INTEGER,
    full_text TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS law_revision_progress (
    day_index INTEGER,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS descriptive_items (
    item_id TEXT PRIMARY KEY,
    exam TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK(item_type IN ('ESSAY', 'PRECIS', 'RC')),
    year INTEGER,
    phase INTEGER,
    paper INTEGER,
    section TEXT,
    subject_id TEXT,
    question_number TEXT,
    prompt_text TEXT NOT NULL,
    topics_json TEXT,
    passage_text TEXT,
    model_answer TEXT,
    model_answers_json TEXT,
    sub_questions_json TEXT,
    marks INTEGER,
    word_limit_min INTEGER,
    word_limit_max INTEGER,
    title_required INTEGER DEFAULT 0,
    incomplete INTEGER DEFAULT 0,
    incomplete_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exam_templates (
    template_id TEXT PRIMARY KEY,
    exam TEXT NOT NULL,
    name TEXT NOT NULL,
    phase INTEGER,
    paper INTEGER,
    total_questions INTEGER,
    marks_per_question REAL,
    total_marks INTEGER,
    time_limit_minutes INTEGER,
    cutoff_pct REAL,
    aggregate_cutoff_pct REAL,
    sections_json TEXT,
    syllabus_units_json TEXT,
    descriptive_components_json TEXT,
    notes TEXT
);

-- Additive question columns (five-option + verification + fact linkage) are
-- applied idempotently by database._ensure_runtime_schema (PRAGMA-checked).

CREATE INDEX IF NOT EXISTS idx_facts_domain ON facts(domain);
CREATE INDEX IF NOT EXISTS idx_fact_topics_topic ON fact_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_fact_subjects_subject ON fact_subjects(subject_id);
CREATE INDEX IF NOT EXISTS idx_pyq_exam_subject ON previous_year_questions(exam, subject_id);
CREATE INDEX IF NOT EXISTS idx_descriptive_exam ON descriptive_items(exam, item_type);

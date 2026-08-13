-- ================================================================
-- MIGRATION: 004_material_categorization.sql
-- PURPOSE: Add material source role tracking for smart routing
-- PHASE: Material Intelligence & PYQ Separation
-- ================================================================

-- Add source_role column to source_documents
-- Values: pyq_phase_paper | regulatory_core | amendment_tracking | essay_examples | supporting_material
ALTER TABLE source_documents ADD COLUMN source_role TEXT DEFAULT 'supporting_material';

-- Create index for efficient role-based filtering
CREATE INDEX IF NOT EXISTS idx_source_documents_role ON source_documents(source_role);

-- Create PYQ_sessions table for separate PYQ attempt tracking
CREATE TABLE IF NOT EXISTS pyq_sessions (
    pyq_id TEXT PRIMARY KEY,
    pyq_source_doc_id INTEGER NOT NULL,
    pyq_title TEXT NOT NULL,
    phase_number INTEGER,
    year INTEGER,
    paper_number INTEGER,
    started_at TEXT,
    submitted_at TEXT,
    total_questions INTEGER,
    score INTEGER,
    accuracy REAL,
    status TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(pyq_source_doc_id) REFERENCES source_documents(doc_id)
);

-- Track PYQ question attempts separately
CREATE TABLE IF NOT EXISTS pyq_question_attempts (
    attempt_id TEXT PRIMARY KEY,
    pyq_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    question_number INTEGER,
    selected_answer TEXT,
    official_answer TEXT,
    is_correct BOOLEAN,
    time_spent_seconds INTEGER,
    marked_for_review BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(pyq_id) REFERENCES pyq_sessions(pyq_id),
    FOREIGN KEY(question_id) REFERENCES questions(question_id)
);

-- Create material usage log for analytics
CREATE TABLE IF NOT EXISTS material_usage_log (
    log_id TEXT PRIMARY KEY,
    source_role TEXT NOT NULL,
    usage_type TEXT,  -- question_generation, essay_grading, search, etc.
    used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_material_usage_role ON material_usage_log(source_role);

-- ================================================================
-- CATEGORIZATION DATA: Will be populated by Python migration script
-- ================================================================

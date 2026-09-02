-- ================================================================
-- MIGRATION: 006_update_tracker.sql
-- PURPOSE: Autonomous agentic amendment/Act update tracker (plan v6,
--          multi-model phase). Stores Google-Search-grounded discoveries
--          with agentic verification rationale + change reasons, and a
--          run log for the perpetual tracker agent.
-- NOTE: All statements are idempotent (IF NOT EXISTS).
-- ================================================================

CREATE TABLE IF NOT EXISTS amendment_updates (
    update_id TEXT PRIMARY KEY,
    exam TEXT NOT NULL DEFAULT 'IFSCA',
    category TEXT NOT NULL DEFAULT 'AMENDMENT',
    title TEXT NOT NULL,
    summary TEXT,
    old_value TEXT,
    new_value TEXT,
    change_reason TEXT,
    verification_rationale TEXT,
    verification_status TEXT NOT NULL DEFAULT 'NEW',
    topic_id TEXT,
    update_date TEXT,
    discovered_at TEXT,
    source_urls_json TEXT,
    search_queries_json TEXT,
    model_used TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tracker_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT,
    finished_at TEXT,
    model_used TEXT,
    searches_json TEXT,
    discovered INTEGER DEFAULT 0,
    verified INTEGER DEFAULT 0,
    contradicted INTEGER DEFAULT 0,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_updates_date ON amendment_updates(COALESCE(update_date, discovered_at));
CREATE INDEX IF NOT EXISTS idx_updates_status ON amendment_updates(status);
CREATE INDEX IF NOT EXISTS idx_updates_category ON amendment_updates(category);

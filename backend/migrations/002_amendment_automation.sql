-- PHASE 2: Amendment Automation Schema
-- Tables for autonomous polling, deduplication, and extraction caching

CREATE TABLE IF NOT EXISTS amendment_source_polls (
    poll_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    polled_at TIMESTAMP NOT NULL,
    new_circulars_found INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS amendment_extraction_cache (
    sha256 TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    published_date TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_content TEXT,
    extraction_status TEXT DEFAULT 'pending',
    amendment_id TEXT REFERENCES amendments(amendment_id)
);

-- Add indexes for efficient polling
CREATE INDEX IF NOT EXISTS idx_amendment_source_polls_source_polled_at
    ON amendment_source_polls(source, polled_at DESC);
CREATE INDEX IF NOT EXISTS idx_amendment_source_polls_status
    ON amendment_source_polls(status);
CREATE INDEX IF NOT EXISTS idx_amendment_extraction_cache_source_extracted_at
    ON amendment_extraction_cache(source, extracted_at DESC);
CREATE INDEX IF NOT EXISTS idx_amendment_extraction_cache_amendment_id
    ON amendment_extraction_cache(amendment_id);

-- ================================================================
-- MIGRATION: 001_content_intelligence.sql
-- PURPOSE: Create FTS5 indexing for 3,571+ source pages
-- PHASE: 0 - Content Intelligence Foundation
-- ================================================================

-- 1. source_documents: metadata for each extracted PDF
CREATE TABLE IF NOT EXISTS source_documents (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    doc_type TEXT,
    extracted_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_file_path TEXT,
    page_count INTEGER,
    total_lines INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. source_chunks: logical chunks of extracted text with metadata
CREATE TABLE IF NOT EXISTS source_chunks (
    chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    chunk_text TEXT NOT NULL,
    section_title TEXT,
    page_num INTEGER,
    chunk_sequence INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES source_documents(doc_id) ON DELETE CASCADE
);

-- 3. FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS source_chunks_fts
USING fts5(
    chunk_text,
    section_title,
    page_num,
    doc_id UNINDEXED,
    chunk_id UNINDEXED,
    content=source_chunks,
    content_rowid=chunk_id
);

-- 4. Trigger to keep FTS5 index in sync with inserts
CREATE TRIGGER IF NOT EXISTS source_chunks_ai AFTER INSERT ON source_chunks BEGIN
  INSERT INTO source_chunks_fts(rowid, chunk_text, section_title, page_num, doc_id, chunk_id)
  VALUES (new.chunk_id, new.chunk_text, new.section_title, new.page_num, new.doc_id, new.chunk_id);
END;

-- 5. Trigger to keep FTS5 index in sync with deletes
CREATE TRIGGER IF NOT EXISTS source_chunks_ad AFTER DELETE ON source_chunks BEGIN
  DELETE FROM source_chunks_fts WHERE chunk_id = old.chunk_id;
END;

-- 6. question_sources: linking questions to authoritative sources
CREATE TABLE IF NOT EXISTS question_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id TEXT NOT NULL,
    source_chunk_id INTEGER NOT NULL,
    authority_score INTEGER DEFAULT 50,
    extraction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(source_chunk_id) REFERENCES source_chunks(chunk_id) ON DELETE CASCADE,
    UNIQUE(question_id, source_chunk_id)
);

-- 7. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_source_docs_category ON source_documents(category);
CREATE INDEX IF NOT EXISTS idx_source_chunks_doc ON source_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_source_chunks_page ON source_chunks(page_num);
CREATE INDEX IF NOT EXISTS idx_question_sources_q ON question_sources(question_id);
CREATE INDEX IF NOT EXISTS idx_question_sources_chunk ON question_sources(source_chunk_id);

-- End of migration

-- Schema Enhancements for Smart Material Management
-- Ensure NO blind sourcing from coaching materials

-- 1. Add classification columns to source_documents
ALTER TABLE source_documents ADD COLUMN purpose_category TEXT DEFAULT 'UNKNOWN';
ALTER TABLE source_documents ADD COLUMN authority_score REAL DEFAULT 0.5 CHECK(authority_score BETWEEN 0.0 AND 1.0);
ALTER TABLE source_documents ADD COLUMN is_qgen_eligible BOOLEAN DEFAULT 1;
ALTER TABLE source_documents ADD COLUMN is_study_eligible BOOLEAN DEFAULT 1;
ALTER TABLE source_documents ADD COLUMN is_reference_only BOOLEAN DEFAULT 0;
ALTER TABLE source_documents ADD COLUMN risk_level TEXT DEFAULT 'GREEN' CHECK(risk_level IN ('GREEN', 'YELLOW', 'RED'));

-- 2. Add classification columns to source_chunks
ALTER TABLE source_chunks ADD COLUMN purpose_category TEXT DEFAULT 'UNKNOWN';
ALTER TABLE source_chunks ADD COLUMN authority_score REAL DEFAULT 0.5 CHECK(authority_score BETWEEN 0.0 AND 1.0);
ALTER TABLE source_chunks ADD COLUMN is_qgen_eligible BOOLEAN DEFAULT 1;

-- 3. Create Master PDF Classification Lookup Table
CREATE TABLE IF NOT EXISTS pdf_classifications (
  doc_name TEXT PRIMARY KEY,
  purpose_category TEXT NOT NULL CHECK(purpose_category IN (
    'OFFICIAL_REGULATORY',
    'ICSI_STUDY_MATERIAL',
    'EXAM_STRUCTURE_META',
    'MEMORY_PAPERS',
    'CONSULTING_INTELLIGENCE',
    'CURRENT_AFFAIRS',
    'COACHING_UNVERIFIED'
  )),
  authority_score REAL NOT NULL CHECK(authority_score BETWEEN 0.0 AND 1.0),
  use_for_qgen BOOLEAN NOT NULL DEFAULT 0,
  use_for_study BOOLEAN NOT NULL DEFAULT 0,
  use_for_reference BOOLEAN NOT NULL DEFAULT 0,
  risk_level TEXT NOT NULL CHECK(risk_level IN ('GREEN', 'YELLOW', 'RED')),
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create Previous Year Questions Table
CREATE TABLE IF NOT EXISTS previous_year_questions (
  pyq_id TEXT PRIMARY KEY,
  year INTEGER NOT NULL,
  phase INTEGER NOT NULL,
  paper INTEGER NOT NULL,
  section TEXT,
  question_number INTEGER,
  question_text TEXT NOT NULL,
  option_a TEXT NOT NULL,
  option_b TEXT NOT NULL,
  option_c TEXT NOT NULL,
  option_d TEXT NOT NULL,
  correct_option TEXT NOT NULL CHECK(correct_option IN ('A', 'B', 'C', 'D')),
  marks INTEGER NOT NULL,
  negative_marking REAL DEFAULT 0.25,
  topic_id TEXT,
  difficulty TEXT CHECK(difficulty IN ('EASY', 'MEDIUM', 'HARD')),

  -- Attempt tracking
  attempted BOOLEAN DEFAULT 0,
  user_answer TEXT,
  is_correct BOOLEAN,
  time_spent_seconds INTEGER,
  attempt_date TEXT,

  -- Source tracking
  source_pdf TEXT NOT NULL,
  source_line_start INTEGER,
  source_line_end INTEGER,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(topic_id) REFERENCES topics(topic_id)
);

-- 5. Create index for fast retrieval
CREATE INDEX IF NOT EXISTS idx_pyq_year_phase ON previous_year_questions(year, phase);
CREATE INDEX IF NOT EXISTS idx_pyq_topic ON previous_year_questions(topic_id);
CREATE INDEX IF NOT EXISTS idx_pyq_attempted ON previous_year_questions(attempted);

-- 6. Create index for source eligibility filtering
CREATE INDEX IF NOT EXISTS idx_source_chunks_qgen_eligible ON source_chunks(is_qgen_eligible, authority_score);
CREATE INDEX IF NOT EXISTS idx_source_docs_qgen_eligible ON source_documents(is_qgen_eligible, authority_score);

-- 7. Populate pdf_classifications with all 150 PDFs

-- TIER 1: OFFICIAL REGULATORY (100% Authority)
INSERT OR REPLACE INTO pdf_classifications VALUES
('013_IFSCA publications__Annual Report 2020-21', 'OFFICIAL_REGULATORY', 0.95, 1, 1, 1, 'GREEN', 'IFSCA official strategic document'),
('014_IFSCA publications__Annual Report 2021-22', 'OFFICIAL_REGULATORY', 0.95, 1, 1, 1, 'GREEN', 'IFSCA official strategic document'),
('015_IFSCA publications__Annual Report 2022-23', 'OFFICIAL_REGULATORY', 0.95, 1, 1, 1, 'GREEN', 'IFSCA official strategic document'),
('016_IFSCA publications__Annual Report 2023-24', 'OFFICIAL_REGULATORY', 0.95, 1, 1, 1, 'GREEN', 'IFSCA official strategic document'),
('098_IFSCA publications__Annual Report 2024-25 English', 'OFFICIAL_REGULATORY', 0.95, 1, 1, 1, 'GREEN', 'Latest IFSCA strategic document'),
('099_IFSCA publications__Annual Report 2024-25 Bilingual', 'OFFICIAL_REGULATORY', 0.95, 1, 1, 1, 'GREEN', 'Latest IFSCA strategic document'),

('017_IFSCA publications__Bulletin Apr-Jun 2024', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Latest regulatory updates'),
('018_IFSCA publications__Bulletin Jul-Sep 2024', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Latest regulatory updates'),
('019_IFSCA publications__Bulletin Oct-Dec 2024', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Latest regulatory updates'),
('020_IFSCA publications__Bulletin Jan-Mar 2025', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Latest regulatory updates'),
('100_IFSCA publications__Bulletin Apr-Jun 2025', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Latest regulatory updates - PRIORITY'),
('101_IFSCA publications__Bulletin Jul-Sep 2025', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Latest regulatory updates - PRIORITY'),
('102_IFSCA publications__Bulletin Oct-Dec 2025', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Latest regulatory updates - PRIORITY'),

('021_IFSCA publications__RI Regulations Consultation 2023', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Exact regulation text'),
('022_IFSCA publications__Draft Payment Services Regulations 2023', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Exact regulation text'),
('024_IFSCA publications__Listing Regulations Consultation 2024', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'Exact regulation text'),
('093-097_IFSCA TAS__*', 'OFFICIAL_REGULATORY', 1.0, 1, 1, 1, 'GREEN', 'TAS Final Regulations 2025'),

-- TIER 2: ICSI STUDY MATERIAL (85% Authority)
('033_ICSI__Paper 4.6 - IFSCA Regulations Listing And Compliances', 'ICSI_STUDY_MATERIAL', 0.95, 1, 1, 1, 'GREEN', 'Official exam study material'),
('037-043_ICSI CSJ__*', 'ICSI_STUDY_MATERIAL', 0.85, 1, 1, 1, 'GREEN', 'Expert regulation interpretation'),
('044-065_ICSI Info Capsule__*', 'ICSI_STUDY_MATERIAL', 0.90, 1, 1, 1, 'GREEN', 'Curated weekly updates'),
('104-113_ICSI Info Capsule__*', 'ICSI_STUDY_MATERIAL', 0.90, 1, 1, 1, 'GREEN', 'Curated weekly updates - LATEST'),
('034_ICSI__Supplement Dec 2025', 'ICSI_STUDY_MATERIAL', 0.95, 1, 1, 1, 'GREEN', 'Updated study material'),
('035_ICSI__Supplement CMSL New Syllabus Dec 2025', 'ICSI_STUDY_MATERIAL', 0.95, 1, 1, 1, 'GREEN', 'Updated study material'),
('036_ICSI__ICSI Earlier IFSCA Note', 'ICSI_STUDY_MATERIAL', 0.60, 0, 1, 1, 'YELLOW', 'Historical - verify against current'),

-- TIER 3: EXAM STRUCTURE / META (Meta-Only)
('001-012_IFSCA career__*', 'EXAM_STRUCTURE_META', 0.0, 0, 0, 1, 'GREEN', 'Exam structure, not content'),
('116_discovered_011_IFSCA-Grade-A-Syllabus', 'EXAM_STRUCTURE_META', 0.0, 0, 1, 1, 'GREEN', 'Exam syllabus reference'),
('117-119_discovered_*_ifsca-*-handout*', 'EXAM_STRUCTURE_META', 0.0, 0, 0, 1, 'GREEN', 'Exam handout - structure only'),
('120_discovered_015_IFSCA-Grade-A-Syllabus', 'EXAM_STRUCTURE_META', 0.0, 0, 0, 1, 'GREEN', 'Exam syllabus'),

-- TIER 4: MEMORY PAPERS (100% Exam Content - Separate PYQ Feature)
('121-124_discovered_*_IFSCA*Grade*A*2024*Memory*Based*', 'MEMORY_PAPERS', 1.0, 0, 0, 1, 'GREEN', 'Actual exam questions - Use PYQ tab'),

-- TIER 5: CONSULTING INTELLIGENCE (50% Authority - Context Only)
('066-075_PwC__*', 'CONSULTING_INTELLIGENCE', 0.50, 0, 0, 1, 'YELLOW', 'Market analysis - context only'),
('115_PwC__FinTech in GIFT IFSC - v2', 'CONSULTING_INTELLIGENCE', 0.50, 0, 0, 1, 'YELLOW', 'Market analysis - context only'),
('080-085_EY__*', 'CONSULTING_INTELLIGENCE', 0.40, 0, 0, 1, 'YELLOW', 'Business analysis - low exam signal'),
('114_EY__Global Commodity Trade via GIFT City 2026', 'CONSULTING_INTELLIGENCE', 0.40, 0, 0, 1, 'YELLOW', 'Business analysis - low exam signal'),
('088-089_Grant Thornton__*', 'CONSULTING_INTELLIGENCE', 0.35, 0, 0, 1, 'YELLOW', 'Illustrative examples only'),
('093-094_KPMG__*', 'CONSULTING_INTELLIGENCE', 0.40, 0, 0, 1, 'YELLOW', 'Market metrics - low exam signal'),

-- TIER 6: CURRENT AFFAIRS (40% Authority - Trend Only)
('107-109_discovered_*All-in-One-Current-Affairs-Booster*', 'CURRENT_AFFAIRS', 0.40, 0, 0, 1, 'YELLOW', 'Coaching booster - unverified'),
('110-112_discovered_CurrentTap*', 'CURRENT_AFFAIRS', 0.40, 0, 0, 1, 'YELLOW', 'Coaching newsletter - unverified'),

-- TIER 7: COACHING/UNVERIFIED (20% Authority - DO NOT USE)
('127-150_Scribd login required__*', 'COACHING_UNVERIFIED', 0.20, 0, 0, 1, 'RED', 'COACHING MATERIAL - DO NOT USE FOR Qgen'),
('125_discovered_IFSCAGENERAL', 'COACHING_UNVERIFIED', 0.20, 0, 0, 1, 'RED', 'Coaching notes - unverified'),
('126_discovered_IFSCALEGAL', 'COACHING_UNVERIFIED', 0.20, 0, 0, 1, 'RED', 'Coaching notes - unverified');

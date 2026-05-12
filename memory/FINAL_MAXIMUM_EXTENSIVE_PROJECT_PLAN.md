# IFSCA Exam Prep Engine - Final Maximum Extensive Project Plan

Generated: 2026-05-10
Workspace: D:\Exam_preparation
Canonical plan file: D:\Exam_preparation\memory\FINAL_MAXIMUM_EXTENSIVE_PROJECT_PLAN.md

This is the final consolidated software plan for the IFSCA Grade A preparation system. It merges:

- The final user vision for a 7-module AI-powered exam preparation engine.
- The original Claude plan files from `C:\Users\Kartik\.claude`.
- The current implementation in `D:\Exam_preparation\backend` and `D:\Exam_preparation\frontend`.
- The research/audit documents already present in the project.
- The 126-PDF corpus summary from `D:\Exam_preparation\COMPLETE_PDF_DIGEST.txt` and `D:\Exam_preparation\memory\ALL_126_PDFS_ANALYSIS.md`.

This document intentionally goes beyond the earlier Claude plans. The earlier plans were useful as a first version, but they are smaller than the actual software that should now be built from the full source corpus.

---

## 1. One-Sentence Product Vision

Build an AI-powered, source-grounded IFSCA Grade A preparation engine that turns 126 collected documents, past exam evidence, user performance history, and live regulatory amendments into a daily adaptive study system with smart mocks, penalty drills, essay grading, amendment tracking, analytics, and an exam-mode interface.

---

## 2. Product Promise

The app is not a generic PDF reader, not a normal mock-test website, and not a loose chatbot.

It is a qualification machine with five hard commitments:

1. It knows the syllabus and the source corpus.
2. It learns the user's weaknesses from every question attempt.
3. It generates mocks using a 60/25/15 allocation toward weak, medium, and strong topics.
4. It treats regulatory amendments as first-class exam events.
5. It grades essays and builds a measurable improvement loop.

The target output is not "more study material." The target output is a student who can repeatedly score in the 85-90 range by exam week because the system has forced the right work at the right time.

---

## 3. Source Corpus Now Available

The project now has a serious corpus. The plan must be built around it, not around a small hand-written topic list.

Known corpus summary from the project:

- Total PDFs: 126.
- Total extracted pages: approximately 3,571.
- Total extracted lines: 190,603.
- Digest file: `D:\Exam_preparation\COMPLETE_PDF_DIGEST.txt`.
- Analysis file: `D:\Exam_preparation\memory\ALL_126_PDFS_ANALYSIS.md`.
- Extracted text location referenced by the analysis: `D:\Exam_preparation\extracted_pdfs`.
- Search index referenced by the analysis: `COMPREHENSIVE_INDEX.json`.

Document categories:

| Category | Count | Role in the software |
|---|---:|---|
| IFSCA career and recruitment documents | 12 | Exam structure, notifications, cutoff history, handouts, result patterns |
| IFSCA annual reports | 6 | Official ecosystem statistics, sector growth, strategic priorities |
| IFSCA quarterly bulletins | 10 | Regulatory updates, recent initiatives, market developments |
| IFSCA regulations and guidelines | 9 | Core legal/regulatory knowledge and amendment source |
| ICSI educational materials | 38 | Primary study explanation layer, especially Paper 4.6 |
| Consulting firm reports | 23 | Business context, tax, sector-level opportunity maps |
| Exam papers and memory-based materials | 4+ | PYQ pattern calibration, difficulty modelling, answer pattern inference |
| Current affairs materials | 6 | Recent economic/regulatory affairs for Paper 1 and essays |
| Miscellaneous handouts/syllabus/results | 6+ | Interface rules, syllabus, official exam instructions |

Key anchor documents:

- ICSI Paper 4.6 - IFSCA Regulations, Listing and Compliances.
- IFSCA Act, 2019.
- IFSCA recruitment notifications for 2022-23, 2024, and 2025.
- IFSCA annual reports 2020-21 through 2024-25.
- IFSCA quarterly bulletins from 2024-2025, including Oct-Dec 2025.
- TAS/TechFin draft, final regulations, transition circular, and FAQs.
- ICSI supplements and Info Capsules through April 2026.
- PwC, EY, Grant Thornton, and KPMG reports on GIFT IFSC, banking, capital markets, fund management, fintech, leasing, tax, and FPI topics.
- Memory papers and discovered syllabus PDFs.

The corpus is sufficient to build the first real knowledge base. More PDFs may improve coverage, but the app should now proceed to ingestion, indexing, and question generation rather than waiting indefinitely.

---

## 4. Final Product Modules

The final app should have nine modules, not merely the seven originally stated. The user's seven modules remain the core user-facing experience, but the source corpus requires two additional infrastructure modules.

### Module 0: Source Vault and Knowledge Engine

Purpose:

- Convert the 126 PDFs and extracted text into a trusted, queryable source base.
- Track each statement back to document, page, line, and topic.
- Prevent hallucinated questions and vague essay feedback.

Required capabilities:

- Register every PDF as a `document`.
- Store PDF metadata: title, category, source URL if known, local path, page count, extraction status, hash, last modified time.
- Split text into chunks with page/line references.
- Deduplicate duplicate documents and duplicate chunks.
- Tag chunks by topic, exam phase, source type, date, and confidence.
- Build SQLite FTS search and optionally vector search later.
- Expose a `source_search` API for question generation, essay feedback, and manual research.

This module is the missing foundation in the current app.

### Module 1: Dashboard Hub

Purpose:

- Serve as the daily control center.
- Tell the student what to do next, not merely show old scores.

Must show:

- Estimated score curve.
- Overall accuracy.
- Phase 1 and Phase 2 readiness.
- Topic heatmap across all tracked topics.
- Weakest 3 topics.
- Smart mock recommendation.
- Penalty drill recommendation.
- Essay trend.
- Amendment mastery status.
- Upcoming amendment review queue.
- Source corpus freshness and ingestion health.

Dashboard decisions should be computed, not hand-written:

- "Take Insurance drill now" if Insurance accuracy has fallen below threshold and attempts are sufficient.
- "Revise TAS FAQs" if a recent amendment has low mastery.
- "Write an essay today" if no essay has been submitted in the past 48 hours.
- "Take full mock" if weak topics have recently improved and the student needs score calibration.

### Module 2: Smart Mock Generator

Purpose:

- Generate a 50-question mock customized to current weakness.

Core algorithm:

- 60 percent questions from weak topics.
- 25 percent questions from medium topics.
- 15 percent questions from strong topics.
- Difficulty curve adapts per topic.
- Amendment-based questions get a recency boost.
- PYQ-like topics get a frequency boost.
- Every generated question must include source references.

The smart mock is the centerpiece of the system. It is currently partially implemented, but it is not yet source-grounded enough.

### Module 3: Penalty Drill Engine

Purpose:

- Force improvement on weak topics through short, targeted drills.

Required drill types:

- Weak topic drill.
- Recent amendment drill.
- Incorrect answer replay.
- Confusing pairs drill.
- PYQ-pattern drill.
- Fact recall drill.
- Application/case drill.
- Final 7-day high-yield drill.

Each drill should produce:

- 10 questions by default.
- Difficulty level.
- Source citations.
- Explanation for every answer.
- Mastery delta after submission.
- Next review date.

### Module 4: Essay Grading Lab

Purpose:

- Improve Phase 2 Paper 1 essay performance through instant scoring and feedback.

Four-rubric grading model:

| Rubric | Marks | What it measures |
|---|---:|---|
| Content accuracy | 25 | Correct facts, relevant arguments, no regulatory mistakes |
| Structure and clarity | 25 | Intro, flow, headings, conclusion, coherence |
| Regulatory knowledge | 25 | IFSCA/GIFT/financial sector depth and correct usage |
| Examples and evidence | 25 | Official data, amendments, sector examples, reports |

Required features:

- Essay prompt bank from current affairs, IFSCA ecosystem, regulations, and ethics/governance themes.
- Timed writing mode.
- AI grading with a structured JSON response.
- Inline feedback.
- Suggested rewrite.
- Model answer outline.
- Source suggestions from the corpus.
- Essay history table.
- Score trend by rubric.
- "Missing evidence" detector that recommends exact sources to cite.

The current implementation grades an essay, but does not yet create a full essay lab.

### Module 5: Amendment Tracker and Amendment Radar

Purpose:

- Treat amendments as live exam events.

Required capabilities:

- Manual amendment entry.
- Seeded amendment database from the existing corpus.
- Automated monitoring of IFSCA, ICSI Info Capsules, bulletins, consultation papers, gazettes, and official publications.
- Diff old vs new values where possible.
- Classify amendment by topic, effective date, importance, and exam probability.
- Auto-generate at least 3 questions per amendment.
- Schedule review until mastered.
- Show "drilled vs pending" status.

Priority amendment themes already identified:

- Fund Management Regulations 2025 and later changes.
- KMP eligibility and PPM validity changes.
- Capital Market Intermediaries Regulations 2025.
- CMI certification deadline.
- KYC Registration Agency Regulations 2025.
- Payment Services Regulations and Payments Regulatory Board developments.
- TechFin and Ancillary Services Regulations 2025.
- TAS transition and FAQs.
- Bullion exchange authorized persons and market access updates.
- AML/CFT/KYC guideline updates.
- Listing Regulations, SPACs, ESG, SGrBs, transition bonds, ISSB S2 alignment.
- Stewardship Code in IFSC.
- Guarantees Regulations 2026.
- Commodity trading hub framework.
- Direct listing and LEAP-related developments.

### Module 6: Analytics and Trends

Purpose:

- Make progress measurable and predictive.

Required analytics:

- Accuracy by topic.
- Accuracy by difficulty.
- Accuracy by source category.
- Accuracy by question type.
- Time per question.
- Mock score trend.
- Drill improvement trend.
- Essay rubric trend.
- Amendment mastery trend.
- Predicted score.
- Confidence interval for predicted score.
- ROI chart: marks gained per hour invested by topic.

The app should answer:

- What is the user's weakest topic?
- Is the weakness recent or historical?
- Is the student over-studying strong topics?
- Which amendment is likely to produce the most marks?
- Is essay structure or content the bigger bottleneck?
- Is the student ready for a full mock today?

### Module 7: History and Context

Purpose:

- Preserve every attempt and every AI-generated artifact.

Must store:

- Uploaded mocks.
- Generated smart mocks.
- All answers.
- All wrong answers.
- All drills.
- All essays.
- All amendment entries.
- All generated questions.
- All AI grading responses.
- All source citations used.
- All recommendations shown to the user.

Nothing should disappear. History is what lets the system adapt.

### Module 8: Exam Mode / TCS iON Familiarization

Purpose:

- Reduce interface shock and improve time discipline.

Must include:

- TCS iON-like mock interface.
- Timer.
- Question palette.
- Mark for review.
- Save and next.
- Clear response.
- Section navigation where applicable.
- Color states for answered, unanswered, marked, answered-and-marked.
- Keyboard-free mouse workflow.
- Final submit confirmation.
- Result screen and review mode.

The earlier plan treated this as optional. In the final product it should be a real module, though still lower priority than source-grounded generation and analytics.

---

## 5. What Claude Correctly Identified

The earlier Claude work got several strategic decisions right.

Correct insight 1: IFSCA is amendment-driven.

The exam is not just a static textbook exam. Recent regulations, circulars, consultations, bulletins, and ICSI capsules matter. This led to the right emphasis on amendment tracking.

Correct insight 2: Weakness tracking should begin from the first mock.

The system should not wait for 5-10 mocks to become useful. Even early data should influence recommendations, while respecting low-confidence sample sizes.

Correct insight 3: Smart mocks are more valuable than random mocks.

The 60/25/15 allocation idea is strong:

- 60 percent weak topics for forced improvement.
- 25 percent medium topics for consolidation.
- 15 percent strong topics for breadth and surprise protection.

Correct insight 4: Essay grading is a major gap.

Most coaching/test-series systems focus on objective questions. The essay component needs structured feedback, examples, and repeated scoring.

Correct insight 5: SQLite + FastAPI + simple frontend is a reasonable first stack.

For a single-user local study engine, this stack is pragmatic and fast.

Correct insight 6: Gemini key rotation can control cost and rate limits.

The app is designed for high-volume question generation and grading. A rotation layer is useful, though it needs hardening.

Correct insight 7: Documentation and audit trail were valuable.

The project already contains useful documents:

- `D:\Exam_preparation\MASTER_PLAN_COMPLETE_DELIVERY.md`
- `D:\Exam_preparation\ULTRAPLAN_v4.0_DELIVERY_EXECUTED.md`
- `D:\Exam_preparation\RESEARCH_VALIDATION_AUDIT.md`
- `D:\Exam_preparation\SMART_MOCK_ARCHITECTURE.md`
- `D:\Exam_preparation\SMART_MOCK_IMPLEMENTATION.md`
- `D:\Exam_preparation\PSEUDOCODE_TO_SOURCE_MAPPING.md`
- `D:\Exam_preparation\memory\FINAL_SOFTWARE_VISION.md`
- `D:\Exam_preparation\memory\ALL_126_PDFS_ANALYSIS.md`

These should now be treated as historical planning inputs, not the final authority.

---

## 6. What Claude Got Wrong or Underspecified

The current system is useful, but some claims in the previous docs overstate readiness.

### Problem 1: "Production-ready" was too generous

The app has a working skeleton and some real algorithms. It is not yet production-ready for the full vision because the knowledge base is not fully seeded into the app's runtime database.

Correct position:

- Prototype: yes.
- Research-validated direction: yes.
- Ready for limited manual use: yes.
- Full source-grounded exam engine: not yet.

### Problem 2: Knowledge base was framework-ready, not implemented

The database has a `knowledge_fts` table, but the source corpus is not yet fully ingested into that table with robust document metadata, chunk references, topic tags, and citations.

Correct requirement:

- Build a real ingestion pipeline before trusting generated questions at scale.

### Problem 3: Question generation is not sufficiently source-grounded

Current generation can call Gemini, but a high-quality exam prep engine must ground every question in one or more document chunks.

Correct requirement:

- Every generated question must store:
  - Source document id.
  - Page number where possible.
  - Source excerpt id or chunk id.
  - Topic.
  - Regulation/amendment reference.
  - Generation prompt version.
  - Verification status.

### Problem 4: Essay grading lacks persistence and calibration

The current endpoint can return a grade, but there is no complete essay history model, trend analysis, calibration set, model answer bank, or rubric evolution.

Correct requirement:

- Add essay tables and UI workflow before calling essay grading complete.

### Problem 5: Amendment automation is not built

Manual amendment recording exists. Auto-detection does not.

Correct requirement:

- Build an amendment radar that monitors official sources and seeds from ICSI/IFSCA corpus first.

### Problem 6: The existing app has duplicate dashboard routes

`D:\Exam_preparation\backend\main.py` currently defines `GET /api/dashboard` twice:

- First route: `get_dashboard_stats()` with response model.
- Second route: `dashboard()` with a different response shape.

Correct requirement:

- Consolidate into one dashboard endpoint with one schema.
- Avoid frontend/backend response mismatch.

### Problem 7: Gemini key rotation needs a no-key guard

`D:\Exam_preparation\backend\gemini_integration.py` builds a key list from environment variables. If no keys are configured, key rotation can fail.

Correct requirement:

- Add explicit startup validation.
- Return a clear error if no keys are present.
- Add a local mock mode for testing without API keys.

### Problem 8: Topic taxonomy is too flat

The current topic list is a decent start, but the full corpus requires a deeper taxonomy:

- Phase.
- Paper.
- Main topic.
- Subtopic.
- Source type.
- Static vs amendment.
- Priority tier.
- Recency.
- Exam probability.

Correct requirement:

- Create a normalized topic taxonomy and map chunks, questions, attempts, and amendments into it.

### Problem 9: PDF digestion happened outside the runtime

The project has a digest file and extracted text, but the app itself cannot yet use the full corpus end to end.

Correct requirement:

- Move from "files exist" to "app can query and cite them."

### Problem 10: Existing success probability claims need caution

Claims like "94% likely qualification" are motivating but not statistically justified unless backed by real user data, cutoff distribution, and calibration across mocks.

Correct requirement:

- Use language like "estimated readiness" and "confidence band."
- Show how the estimate was computed.
- Avoid fake precision.

---

## 7. Current Implementation Inventory

### Backend

Location:

- `D:\Exam_preparation\backend`

Implemented files:

- `main.py`
- `database.py`
- `models.py`
- `gemini_integration.py`
- `requirements.txt`

Current API endpoints:

| Endpoint | Status | Notes |
|---|---|---|
| `GET /health` | Implemented | Checks API and database state |
| `POST /api/upload-mock` | Implemented | Records mock question attempts |
| `GET /api/weak-topics` | Implemented | Returns weak topics below threshold |
| `POST /api/penalty-drill` | Implemented | Generates drill via Gemini |
| `POST /api/grade-essay` | Implemented | Grades essay via Gemini |
| `POST /api/record-amendment` | Implemented | Stores amendment and can trigger question generation |
| `GET /api/dashboard` | Implemented twice | Needs consolidation |
| `POST /api/generate-smart-mock` | Implemented | Uses weakness ranking and Gemini generation |
| `GET /` | Implemented | API info |

Current database tables:

| Table | Status | Purpose |
|---|---|---|
| `question_attempts` | Implemented | Individual question attempts |
| `topic_stats` | Implemented | Topic-level accuracy |
| `amendments` | Implemented | Manual amendment storage |
| `generated_questions` | Implemented | Cache generated questions |
| `mocks` | Implemented | Mock-level summary |
| `penalty_drills` | Implemented | Drill summary |
| `knowledge_fts` | Created | Needs population and lifecycle |
| `smart_mocks` | Implemented | Stores smart mock metadata |

Current smart mock functions:

- `calculate_weakness_score(topic)`
- `rank_topics_by_weakness()`
- `allocate_question_slots(ranked_topics, total_questions=50)`
- `save_smart_mock(...)`
- `get_smart_mock_config()`
- `generate_smart_mock_questions(...)`

Current topic list:

- `PH2_FM_REGS`
- `PH2_BANKING`
- `PH2_CAPITAL`
- `PH2_TECHFIN`
- `PH2_IFSCA`
- `PH2_BULLION`
- `PH2_CMI`
- `PH2_INSURANCE`
- `PH2_AML_KYC`
- `PH2_LISTING`
- `PH2_PAYMENT`
- `PH2_ECONOMICS`
- `PH2_AMENDMENTS`

This list should be expanded but not thrown away.

### Frontend

Location:

- `D:\Exam_preparation\frontend\index.html`

Current status:

- Single-page HTML/JS dashboard.
- Mock upload UI.
- Weak topic display.
- Penalty drill UI.
- Essay grading UI.
- Amendment entry UI.
- Smart mock generation UI.

Required next step:

- Split large single file later only if needed.
- First fix data flows and source-grounding.

### Documentation

Existing docs are extensive but fragmented. This file should become the new north star.

Previous docs should remain as history:

- Original practical plan.
- Effort max plans.
- Delivery execution plan.
- Research validation audit.
- Smart mock architecture.
- Smart mock implementation.
- PDF analysis.

---

## 8. Final Architecture

### Layer 1: Source Layer

Inputs:

- Local PDFs.
- Extracted text files.
- Digest file.
- Official links collected earlier.
- User-uploaded future PDFs.
- ICSI Info Capsules.
- IFSCA publications and bulletins.
- Scribd/PYQ memory materials when available locally.

Outputs:

- `documents`
- `document_chunks`
- `source_citations`
- `document_topics`
- `document_events`

### Layer 2: Knowledge Layer

Responsibilities:

- FTS search.
- Topic tagging.
- Amendment extraction.
- High-yield scoring.
- Source citation retrieval.
- Duplicate detection.

Optional later:

- Embeddings/vector search.
- Cross-document entity graph.
- Regulation diffing.

### Layer 3: Exam Intelligence Layer

Responsibilities:

- Weakness scoring.
- Smart mock allocation.
- Drill recommendation.
- Amendment priority scoring.
- Essay rubric grading.
- Readiness estimation.
- Review scheduling.

### Layer 4: AI Layer

Responsibilities:

- Question generation.
- Explanation generation.
- Essay grading.
- Amendment extraction.
- Topic classification.
- Source-to-question conversion.

Rules:

- AI must receive retrieved source context whenever generating official/regulatory questions.
- AI output must be JSON.
- AI output must be validated before storing.
- AI output must not be trusted if citation is missing for regulatory facts.

### Layer 4B: Gemini 3.0-Flash AI Model Specification

**Model Selection:**

- Model ID: `gemini-3-flash-preview`
- Release: December 17, 2025
- Class: Frontier-class performance at fraction of cost
- Input tokens: 1,048,576 (1M context window)
- Output tokens: 65,536 (64K)
- Cost: ~$0.075 per 1M input tokens

**Supported Input Types:**

- Text
- Images (inline base64)
- Video
- Audio
- PDF documents

**Output:** Text only

**AI Operations to Implement:**

| Operation | API Endpoint | Purpose | Latency | Cost |
|-----------|--------------|---------|---------|------|
| Question generation | POST /generateContent | Generate exam questions from source chunks | <3s (streaming) | Full rate |
| Essay grading | POST /generateContent | Grade 4-rubric essay submissions | <5s | Full rate |
| Amendment extraction | POST /generateContent | Extract regulatory changes from documents | <3s | Full rate |
| Topic classification | POST /generateContent | Auto-tag corpus chunks | Batch (50% off) | 50% discount |
| Explanation generation | POST /generateContent | Create answer explanations | <2s | Full rate |

**Real-time Capabilities:**

1. **SSE Streaming** (Server-Sent Events):
   - Endpoint: `POST /v1beta/models/gemini-3-flash-preview:streamGenerateContent?alt=sse`
   - Use case: Real-time dashboard updates, progressive response display
   - Events: `interaction.start`, `content.start`, `content.delta`, `content.stop`, `interaction.complete`, `error`

2. **Batch API** (Asynchronous Processing):
   - Endpoint: `POST /v1beta/models/gemini-3-flash-preview:batchGenerateContent`
   - Cost: 50% discount
   - Turnaround: ~24 hours
   - Use case: Bulk question generation (100+ questions)
   - Rate limiting: Suitable for overnight bulk operations

3. **Context Caching** (Persistent Reuse):
   - Cost: 50% discount on cached reads
   - Use case: Repeated queries on same study documents
   - Lifecycle: Cache persists for 1 hour; auto-expires if unused
   - Example: Cache all ICSI Paper 4.6 text for instant amendment queries

**Gemini 3.0-Flash vs Previous Models:**

| Feature | Gemini 3.0 Flash | Gemini 2.5 Pro | Notes |
|---------|-----------------|----------------|-------|
| Context Window | 1M | 2M | 3.0 Flash sufficient for exam prep; faster |
| Speed | ⚡⚡⚡ Fast | ⚡ Moderate | 3.0 Flash 5-10x faster |
| Cost | $0.075/1M input | $0.15+/1M input | 3.0 Flash 50% cheaper |
| Reasoning | Good | Excellent | 3.0 Flash handles exam questions well |
| Streaming | ✅ SSE | ✅ SSE | Both support SSE |
| Batch | ✅ Yes | ✅ Yes | Both available |
| Caching | ✅ Yes | ✅ Yes | Both available |

**Question Generation Strategy:**

```
1. Retrieve source chunks (deterministic, no AI cost)
2. Send to Gemini with examples and constraints:
   - "Generate 5 IFSCA regulation questions from this TechFin chunk"
   - "Difficulty: medium"
   - "Include 4 options, one correct answer"
   - "Include 2-sentence explanation citing the source"
3. Validate JSON structure (no AI needed)
4. Check for citation presence (required before storage)
5. Deduplicate against existing question bank
6. Store with source reference (document_id, chunk_id, page)
```

**Essay Grading Workflow:**

```
1. User submits essay (text only)
2. Compute structural metrics (word count, paragraph count)
3. Retrieve relevant source chunks for the topic
4. Send to Gemini 3.0-Flash with:
   - Essay text
   - Rubric definitions (4 x 25 points)
   - Retrieved source context
   - Prompt: "Grade this IFSCA essay using the rubrics. Return JSON."
5. Parse JSON response:
   - content_accuracy: 0-25
   - structure_clarity: 0-25
   - regulatory_knowledge: 0-25
   - examples_evidence: 0-25
   - Overall: sum of four rubrics (0-100)
6. Store scores and feedback in database
7. Update essay trend dashboard
```

**Cost Optimization Strategy:**

| Operation | Method | Savings | Frequency |
|-----------|--------|---------|-----------|
| Bulk question generation | Batch API at night | 50% | 1x per week |
| Repeated essay/drill queries | Context Caching on PDF | 50% | Ongoing |
| Single question gen | Streaming real-time | 0% | On demand |
| Topic classification | Batch preprocessing | 50% | 1x during setup |

**Estimated Monthly Cost (12-week exam prep):**

```
Scenario: 2,000 questions generated + 50 essays graded + 10 mocks reviewed

Standard pricing:
- 2,000 questions @ 400 tokens avg: 800K input tokens @ $0.075 = $60
- 50 essays @ 500 tokens avg: 25K input tokens @ $0.075 = $2
- Explanations & metadata: 100K input @ $0.075 = $7.50
Total standard: $69.50

With optimizations:
- 1,000 questions via Batch (50% off): $30
- 1,000 questions real-time: $30
- 50 essays with cache (50% off): $1
- Bulk operations: $5
Total optimized: $66

Savings: ~5% (modest; real value is speed + reliability)
Budget: ₹60-75 for entire 12-week prep
```

**Context Caching Strategy for Exam Prep Corpus:**

Context caching reduces cost by 50% on cache hits. For exam prep, this is most valuable for repeated queries on same documents.

```python
class CacheManager:
    """Manage caches for frequently-accessed source documents."""

    def __init__(self, gemini_client):
        self.client = gemini_client
        self.cache_store = {}  # {document_id: cache_name}
        self.cache_expiry = {}  # {document_id: expiry_timestamp}

    async def create_cache_for_document(self, document_id, document_text):
        """
        Create a persistent cache for a source document.

        Cost: Full price for cache creation (input tokens counted)
        Benefit: All subsequent queries on this cache cost 50% less

        Cache persists for 1 hour from last use, then auto-deletes.
        """
        try:
            # Upload document to cache
            cache_config = {
                "contents": [
                    {
                        "parts": [
                            {"text": f"Source document for exam preparation:\n{document_text}"}
                        ]
                    }
                ],
                "system_instruction": (
                    "You are an IFSCA exam expert. Answer questions about this document precisely. "
                    "Always cite the source text."
                ),
                "ttl": "3600s"  # 1 hour
            }

            cache = await self.client.caches.create(
                model="gemini-3-flash-preview",
                config=cache_config,
            )

            self.cache_store[document_id] = cache.name
            self.cache_expiry[document_id] = time.time() + 3600

            logging.info(f"Cache created for document {document_id}: {cache.name}")
            return cache.name

        except Exception as e:
            logging.error(f"Cache creation failed for {document_id}: {e}")
            return None

    async def query_cached_document(self, document_id, query):
        """
        Query a cached document (50% cost savings).

        Usage is transparent - returns same as non-cached query but cheaper.
        """
        cache_name = self.cache_store.get(document_id)
        if not cache_name:
            # No cache, fall back to non-cached retrieval
            return await self.query_document_uncached(document_id, query)

        try:
            response = await self.client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=query,
                config={
                    "cached_content": cache_name
                }
            )
            return response

        except Exception as e:
            logging.warning(f"Cached query failed: {e}, retrying uncached")
            return await self.query_document_uncached(document_id, query)

    def list_active_caches(self):
        """Show all active caches for admin dashboard."""
        return {
            doc_id: {
                "cache_id": cache_name,
                "expires_at": self.cache_expiry.get(doc_id)
            }
            for doc_id, cache_name in self.cache_store.items()
        }

# Usage in question generation:
# 1. On document ingest: Create cache
# 2. During question generation: Use cached retrieval
# 3. Cost savings accumulate over time

class CachingQuestionGenerator:
    def __init__(self, cache_manager):
        self.cache_mgr = cache_manager

    async def generate_from_chunk(self, chunk_id, topic_id):
        """
        Generate questions with automatic caching.

        Flow:
        1. Retrieve chunk from database
        2. Find parent document_id
        3. Check if document has cache
        4. If no cache: Create cache (cost: full price)
        5. Query cache: Generate questions (cost: 50% of normal)
        """
        chunk = get_chunk(chunk_id)
        document_id = chunk.document_id
        document_text = get_document_full_text(document_id)

        # Ensure cache exists
        if document_id not in self.cache_mgr.cache_store:
            await self.cache_mgr.create_cache_for_document(
                document_id,
                document_text
            )

        # Now query via cache
        query = f"""
Generate 5 exam-style questions from this document chunk about {topic_id}.
Return JSON array with: question_text, option_a, option_b, option_c, option_d,
correct_answer (A/B/C/D), explanation, difficulty (easy/medium/hard).
"""
        response = await self.cache_mgr.query_cached_document(
            document_id,
            query
        )

        return response
```

**Batch API for Overnight Question Seeding:**

```python
import asyncio
from datetime import datetime

class BatchQuestionSeeder:
    """Generate large batches of questions overnight using Batch API."""

    def __init__(self, gemini_client):
        self.client = gemini_client

    async def seed_questions_batch(self, topic_configs):
        """
        Create a batch job to seed 1000+ questions overnight.

        Input: List of {topic_id, num_questions, difficulty_mix}
        Output: JSONL file with generated questions
        Cost: 50% discount on batch pricing
        Turnaround: ~4-24 hours
        """

        # Build JSONL request file
        requests = []
        request_id = 0

        for config in topic_configs:
            topic_id = config["topic_id"]
            num_questions = config["num_questions"]

            # Retrieve source chunks for this topic
            chunks = search_chunks_by_topic(topic_id, limit=10)

            for i in range(num_questions):
                difficulty = config["difficulty_mix"][i % 3]  # Cycle easy/med/hard
                chunk = chunks[i % len(chunks)]

                request = {
                    "key": f"topic_{topic_id}_q{i}",
                    "request": {
                        "contents": [{
                            "parts": [{
                                "text": f"""
Generate 1 IFSCA exam question about {topic_id}.

Source context:
{chunk.text[:500]}

Requirements:
- Difficulty: {difficulty}
- Format: JSON with fields: question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, difficulty
- Must cite the source in explanation
- Answer must be single letter (A/B/C/D)
"""
                            }]
                        }],
                        "generation_config": {
                            "response_mime_type": "application/json"
                        }
                    }
                }
                requests.append(request)
                request_id += 1

        # Create batch job
        batch_job = await self.client.batches.create(
            model="gemini-3-flash-preview",
            src=requests,  # Inlined requests (< 20MB)
            config={
                "displayName": f"exam-seed-batch-{datetime.now().isoformat()}"
            }
        )

        logging.info(f"Batch job created: {batch_job.name}")
        return batch_job.name

    async def monitor_batch_job(self, batch_name):
        """
        Poll batch job status until completion.

        States: PROCESSING, SUCCEEDED, FAILED, CANCELLED, EXPIRED
        """
        while True:
            batch = await self.client.batches.get({"name": batch_name})

            status = batch.state
            logging.info(f"Batch {batch_name}: {status}")

            if status in ["JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED"]:
                return batch

            # Wait 60 seconds before polling again
            await asyncio.sleep(60)

    async def retrieve_batch_results(self, batch_name):
        """
        Download and process batch results once completed.

        Output format: JSONL with one response per line
        """
        batch = await self.client.batches.get({"name": batch_name})

        if batch.state != "JOB_STATE_SUCCEEDED":
            logging.error(f"Batch {batch_name} did not succeed: {batch.state}")
            return []

        # Download result file
        result_file_name = batch.dest.fileName
        result_content = await self.client.files.download({
            "file": result_file_name
        })

        questions_saved = 0
        for line in result_content.decode('utf-8').split('\n'):
            if not line.strip():
                continue

            try:
                response_obj = json.loads(line)
                question_data = response_obj.get("response", {})

                # Parse and validate
                question = GeneratedQuestion(**question_data)

                # Save to database
                save_question(question)
                questions_saved += 1

            except Exception as e:
                logging.error(f"Failed to process batch result line: {e}")

        logging.info(f"Batch complete: {questions_saved} questions saved")
        return questions_saved

    async def full_seed_workflow(self, topic_configs):
        """
        End-to-end: Create batch -> Monitor -> Retrieve -> Save
        """
        # 1. Create batch
        batch_name = await self.seed_questions_batch(topic_configs)

        # 2. Monitor (can be async, run in background)
        batch = await self.monitor_batch_job(batch_name)

        # 3. Retrieve results
        if batch.state == "JOB_STATE_SUCCEEDED":
            count = await self.retrieve_batch_results(batch_name)
            return {"success": True, "questions_generated": count}
        else:
            return {"success": False, "error": batch.state}

# Usage example: Run overnight
# batch_seeder = BatchQuestionSeeder(gemini_client)
# asyncio.run(batch_seeder.full_seed_workflow([
#     {"topic_id": "PH2_FM_REGS", "num_questions": 100, "difficulty_mix": ["easy", "medium", "hard"]},
#     {"topic_id": "PH2_BANKING", "num_questions": 100, "difficulty_mix": ["easy", "medium", "hard"]},
#     ...
# ]))
```

---

**Implementation Rules:**

1. **Every question must have a source citation before storage.**
   - Stored fields: document_id, chunk_id, page_number_start, page_number_end
   - Validation: Reject AI output if citation missing

2. **All AI outputs must be JSON-formatted and validated.**
   - First: Check JSON parse
   - Second: Check all required fields present
   - Third: Check field types (e.g., difficulty in [easy, medium, hard])
   - Fourth: Check values within bounds (e.g., rubric scores 0-25)

3. **Streaming is default for interactive operations.**
   - Dashboard drills: SSE for real-time updates
   - Mock questions: SSE for progressive generation
   - Essay feedback: SSE for streamed grading

4. **Batch is default for bulk operations.**
   - Question seeding (100+ questions)
   - Topic classification (all chunks)
   - Amendment extraction (new PDFs)

5. **Caching strategy for documents:**
   - Create cache on document ingest for PDF chunks
   - Reuse cache for topic classification, question generation, essay context
   - Expire cache if document is replaced

6. **No AI call should block critical paths.**
   - Dashboard loads even if question generation fails
   - Essay submission succeeds even if Gemini is down (grade later)
   - Mocks load from cache while new questions generate in background

**Advanced Function Calling for Amendment Extraction:**

Function calling allows Gemini to trigger backend operations during conversation. Use for amendment processing:

```python
from google.genai import types

amendment_extraction_functions = [
    types.FunctionDeclaration(
        name="extract_amendment",
        description="Extract regulatory amendment details from document text",
        parameters={
            "type": "object",
            "properties": {
                "regulation_name": {
                    "type": "string",
                    "description": "Name of regulation being amended (e.g., 'Fund Management Regulations 2024')"
                },
                "old_value": {
                    "type": "string",
                    "description": "Previous requirement or value"
                },
                "new_value": {
                    "type": "string",
                    "description": "Updated requirement or value"
                },
                "effective_date": {
                    "type": "string",
                    "description": "Date when amendment becomes effective (YYYY-MM-DD)"
                },
                "topic_id": {
                    "type": "string",
                    "description": "IFSCA exam topic this amendment affects"
                },
                "exam_probability": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Likelihood this will be tested"
                },
                "impact_summary": {
                    "type": "string",
                    "description": "1-2 sentence summary of what this amendment changes"
                }
            },
            "required": ["regulation_name", "new_value", "effective_date", "topic_id"]
        }
    )
]

class AmendmentExtractor:
    """Extract amendments from documents using Gemini function calling."""

    def __init__(self, gemini_client):
        self.client = gemini_client

    async def extract_amendments_from_document(self, document_id, document_text):
        """
        Use function calling to extract structured amendments from a document.

        Flow:
        1. Send document + function definitions to Gemini
        2. Gemini analyzes and calls extract_amendment multiple times
        3. Collect all function calls
        4. Save each amendment to database with citation
        5. Auto-generate 3 questions per amendment
        """

        tool_config = types.Tool(
            function_declarations=amendment_extraction_functions
        )

        response = self.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=f"""
Analyze this document for regulatory amendments affecting IFSCA exams.
For each amendment found, call the extract_amendment function.

Document:
{document_text}

Instructions:
- Extract ALL amendments, not just major ones
- If effective date not stated, mark as TBD
- Classify exam_probability based on topic importance
- Use existing topic_ids from: {self.get_valid_topic_ids()}
- For each extraction, ensure at least old_value XOR new_value is provided
""",
            config=types.GenerateContentConfig(
                tools=[tool_config],
                include_server_side_tool_invocations=True
            )
        )

        # Collect function calls
        amendments_extracted = []
        for part in response.candidates[0].content.parts:
            if part.function_call:
                amendment_data = part.function_call.args

                # Validate extracted amendment
                try:
                    amendment = Amendment(
                        **amendment_data,
                        source_document_id=document_id,
                        source_chunk_id="full_document",
                        extracted_by_ai=True
                    )

                    # Save to database
                    amendment_id = save_amendment(amendment)

                    # Generate 3 questions per amendment
                    await self.generate_amendment_questions(
                        amendment_id,
                        amendment
                    )

                    amendments_extracted.append(amendment_id)

                except Exception as e:
                    logging.error(f"Invalid amendment extraction: {e}")

        return amendments_extracted

    async def generate_amendment_questions(self, amendment_id, amendment):
        """Auto-generate 3 exam-style questions for this amendment."""

        prompt = f"""
Generate 3 exam-level questions about this amendment:

Regulation: {amendment.regulation_name}
Old value: {amendment.old_value}
New value: {amendment.new_value}
Effective: {amendment.effective_date}
Topic: {amendment.topic_id}

Requirements:
- Difficulty: medium to hard
- Answer format: Multiple choice (A/B/C/D)
- Include explanation mentioning the specific change
- Format: JSON array with objects {question_text, option_a, option_b, option_c, option_d, correct_answer, explanation}
"""

        response = await self.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        questions_data = json.loads(response.text)
        for i, question_data in enumerate(questions_data):
            question_data["amendment_id"] = amendment_id
            question_data["source_document_id"] = amendment.source_document_id
            question_data["is_amendment_based"] = True

            question = GeneratedQuestion(**question_data)
            save_question(question)

        return len(questions_data)
```

**Multimodal Capabilities for Exam Preparation:**

While the primary use is text-based, Gemini supports images, videos, and audio for enhanced features:

```python
class MultimodalExamHelper:
    """Leverage multimodal capabilities for richer exam prep."""

    async def analyze_chart_or_diagram(self, image_path, topic_id):
        """
        Process charts, flowcharts, regulatory diagrams from PDFs.

        Use case: Convert scanned diagrams to text explanations
        """
        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        response = await self.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_data
                    }
                },
                {
                    "text": f"Explain this regulatory diagram for IFSCA {topic_id}. Format: JSON with title, key_elements, explanation, questions."
                }
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        diagram_data = json.loads(response.text)
        return diagram_data

    async def extract_text_from_scanned_pdf(self, image_path):
        """
        If a PDF page is scanned (image), extract text via OCR.

        Use case: Handle low-quality or image-format PDFs
        """
        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        response = await self.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                },
                {
                    "text": "Extract all text from this page precisely. Format as JSON with 'extracted_text' field."
                }
            ]
        )

        extracted = json.loads(response.text)
        return extracted["extracted_text"]

    async def generate_exam_question_from_image(self, image_path, difficulty="medium"):
        """
        Generate a question based on an image (chart, screenshot, etc).

        Use case: Create questions from exam paper screenshots
        """
        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        response = await self.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_data
                    }
                },
                {
                    "text": f"""Generate 1 exam question about this image.
Difficulty: {difficulty}
Format: JSON with question_text, option_a, option_b, option_c, option_d, correct_answer, explanation"""
                }
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        return json.loads(response.text)
```

**Key Gemini Endpoints Used:**

```
POST /v1beta/models/gemini-3-flash-preview:generateContent
  → Single question/essay operation (real-time)

POST /v1beta/models/gemini-3-flash-preview:streamGenerateContent
  → Real-time streaming for UI (SSE)

POST /v1beta/models/gemini-3-flash-preview:batchGenerateContent
  → Bulk operations (50% discount, 24h turnaround)

POST /v1beta/caches (for Gemini 2.0+)
  → Create cache from document chunks (if upgrading)

POST /v1beta/cachedContents
  → Use cached content for repeated queries

POST /v1beta/interactions
  → Multi-turn conversations with streaming tool calls

wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent
  → WebSocket for real-time audio (future feature)
```

**Failure Handling:**

| Failure | Impact | Recovery |
|---------|--------|----------|
| Gemini API rate limit | Question gen delayed | Queue request, retry in 60s, use cached questions |
| Gemini API down | No new questions generated | Use existing question bank + cached mocks |
| Invalid JSON response | Question not stored | Log error, retry prompt with stricter constraints |
| Missing citation | Question rejected | Regenerate with stricter prompt |
| Expired API keys | All endpoints fail | Alert user, local mock mode active |
| Stream timeout (> 30s) | Progressive render halts | Fall back to full response served at once |
| Cache expired | Subsequent queries at full price | Transparently re-create cache |

---

**Advanced Gemini 3.0-Flash Features for Exam Prep:**

1. **Live API (WebSocket for Real-Time Audio Interaction)**
   - Endpoint: `wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={API_KEY}`
   - Model: `gemini-3.1-flash-live-preview`
   - Use case: Future feature - Live spoken amendment Q&A or exam simulation with voice interface
   - Features:
     - Real-time bidirectional audio streaming
     - Audio input with transcription output
     - Lower latency than HTTP for interactive sessions
   - Configuration:
     ```json
     {
       "config": {
         "model": "models/gemini-3.1-flash-live-preview",
         "responseModalities": ["AUDIO"],
         "inputAudioTranscription": {},
         "systemInstruction": {
           "parts": [{"text": "You are an IFSCA exam expert. Answer questions concisely."}]
         }
       }
     }
     ```

2. **Interactions API (Streaming Tool Calls)**
   - Endpoint: `POST /v1beta/interactions`
   - Purpose: Multi-turn conversations with function calling and streaming
   - Event types: `interaction.start`, `content.start`, `content.delta`, `content.stop`, `interaction.complete`, `error`
   - Use case: Interactive drill feedback, amendment Q&A loops
   - Streaming tool calls allow real-time function execution during generation
   - Tool calls arrive as `content.delta` events with complete JSON arguments

3. **Multimodal Function Responses**
   - Questions can include inline images (e.g., charts from exam papers)
   - Function results can return both text and image data (base64)
   - Use case: Chart-based questions, visual regulatory diagrams, amendment illustrations
   - Example: Return an IFSCA regulatory structure diagram with question

4. **Dynamic Thinking Levels** (Gemini 3 feature)
   - `thinkingLevel: "low"` - Fast questions (exam drills)
   - `thinkingLevel: "medium"` - Balanced (smart mocks)
   - `thinkingLevel: "high"` - Deep reasoning (essay feedback analysis)
   - Cost impact: Higher thinking = higher latency but better quality
   - Recommendation for exam prep: Use "low" for drills, "medium" default for mocks

5. **Batch Processing with File Upload**
   - Upload JSONL file with 100+ requests
   - Automatic retry and failure tracking
   - File management: `ai.files.upload()`, `ai.files.download()`
   - Completion window: `"24h"` is standard
   - Ideal for: Sunday-Thursday overnight question seed generation (1000 questions)

6. **Vision Capabilities (Image Understanding)**
   - Extract text from scanned PDFs (OCR)
   - Analyze diagrams and flowcharts
   - Process exam paper screenshots
   - Use case: When source PDFs are images, convert to searchable chunks
   - Supported formats: PNG, JPEG, GIF, WebP

7. **OpenAI-Compatible API**
   - Base URL: `https://generativelanguage.googleapis.com/v1beta/openai/`
   - Allows drop-in replacement if needed later
   - Useful for: Using OpenAI-based libraries/frameworks with Gemini backend
   - Example: LangChain, LlamaIndex integration compatibility

**Multi-Key Rotation Strategy (11+ Keys for Maximum Resilience):**

With 11+ API keys, you can handle significantly higher throughput and maintain resilience even if multiple keys hit rate limits simultaneously.

```python
import os
import time
from collections import deque
from datetime import datetime

# Load all available keys (up to 20)
GEMINI_KEYS = [
    os.getenv(f"GEMINI_API_KEY_{i}")
    for i in range(1, 21)
]
ACTIVE_KEYS = [k for k in GEMINI_KEYS if k]

class GeminiKeyManager:
    """Advanced key rotation with 11+ key support."""

    def __init__(self):
        self.keys = ACTIVE_KEYS
        self.key_count = len(self.keys)
        self.current_index = 0
        self.rate_limit_until = {}  # {key: expiry_timestamp}
        self.key_usage_stats = {k: {"calls": 0, "errors": 0} for k in self.keys}
        self.key_health = {k: "healthy" for k in self.keys}

        if self.key_count < 5:
            raise ValueError(f"At least 5 keys recommended; got {self.key_count}")

        logging.info(f"Gemini Key Manager initialized with {self.key_count} keys")

    def get_next_key(self):
        """
        Intelligent key selection:
        1. Skip rate-limited keys
        2. Prefer keys with lowest usage
        3. Round-robin among healthy keys
        """
        available_keys = self._get_available_keys()

        if not available_keys:
            logging.warning(f"All {self.key_count} keys rate-limited; using least-limited")
            return min(self.rate_limit_until.items(), key=lambda x: x[1])[0]

        # Prefer key with lowest call count
        best_key = min(
            available_keys,
            key=lambda k: self.key_usage_stats[k]["calls"]
        )

        self.key_usage_stats[best_key]["calls"] += 1
        return best_key

    def _get_available_keys(self):
        """Return list of keys not currently rate-limited."""
        current_time = time.time()
        available = []

        for key in self.keys:
            if key not in self.rate_limit_until:
                available.append(key)
            elif current_time > self.rate_limit_until[key]:
                # Rate limit expired, key is available again
                del self.rate_limit_until[key]
                available.append(key)

        return available

    def mark_rate_limited(self, key, retry_after_seconds=60):
        """Mark a key as rate-limited after 429 error."""
        self.rate_limit_until[key] = time.time() + retry_after_seconds
        self.key_health[key] = "rate_limited"
        self.key_usage_stats[key]["errors"] += 1

        logging.warning(
            f"Key rate-limited | Available: {len(self._get_available_keys())}/{self.key_count} | "
            f"Retry in {retry_after_seconds}s"
        )

    def mark_unhealthy(self, key, reason="api_error"):
        """Mark a key as unhealthy (quota exceeded, auth error, etc)."""
        self.key_health[key] = "unhealthy"
        self.key_usage_stats[key]["errors"] += 1

        logging.error(f"Key marked unhealthy: {reason}")

    def get_health_status(self):
        """Return overall key manager health."""
        available = len(self._get_available_keys())
        healthy = sum(1 for h in self.key_health.values() if h == "healthy")

        return {
            "total_keys": self.key_count,
            "available_keys": available,
            "healthy_keys": healthy,
            "rate_limited_keys": len(self.rate_limit_until),
            "keys": {
                k: {
                    "status": self.key_health[k],
                    "calls": self.key_usage_stats[k]["calls"],
                    "errors": self.key_usage_stats[k]["errors"],
                    "error_rate": self.key_usage_stats[k]["errors"] / max(self.key_usage_stats[k]["calls"], 1)
                }
                for k in self.keys
            }
        }

    def get_load_distribution(self):
        """Show how load is distributed across keys."""
        total_calls = sum(s["calls"] for s in self.key_usage_stats.values())

        return {
            "total_calls": total_calls,
            "distribution": {
                k: {
                    "calls": self.key_usage_stats[k]["calls"],
                    "percent": 100 * self.key_usage_stats[k]["calls"] / max(total_calls, 1)
                }
                for k in self.keys
            }
        }
```

**Load Distribution Across 11+ Keys:**

```python
# With 11+ keys:
# - Each key handles ~1/11 of QPM limit
# - Free tier: 60 QPM / 11 keys ≈ 5.5 QPM per key (burst capacity)
# - One key exhausted? Use remaining 10 keys
# - Two keys exhausted? Still have 9 keys available
# - Multiple keys can scale to match "Pro" tier limits

# Example capacity calculation:
# - 11 keys × 60 QPM (free) = 660 QPM total burst capacity
# - 11 keys × 1,500 RPD (free) = 16,500 RPD total capacity
# - Exam prep needs: ~24 questions/day = 0.017 QPM (well under limit)
```

**Rate Limiting and Quota Management:**

| Tier | QPM (Queries Per Minute) | RPD (Requests Per Day) | Strategy |
|------|--------------------------|------------------------|----------|
| Free | 60 | 1,500 | Use batch for bulk, single keys sufficient |
| Pro | 1,000 | 10 million | Use 3-5 keys, round-robin rotation |
| Enterprise | Custom | Custom | Contact Google Cloud sales |

**For exam prep (estimated usage):**
- 2,000 questions over 12 weeks = ~24 questions/day
- 50 essays over 12 weeks = ~6 essays/day
- 10 smart mocks (~500 questions) = heavy on specific days
- **Free tier sufficient** if using batch for bulk + key rotation for spikes

**Monitoring and Observability:**

```python
import logging
from datetime import datetime

class GeminiMetrics:
    def __init__(self):
        self.calls_total = 0
        self.calls_failed = 0
        self.tokens_input_total = 0
        self.tokens_output_total = 0
        self.cost_total = 0.0
        self.latencies = []

    def log_call(self, operation, latency_ms, input_tokens, output_tokens, cost):
        """Track single Gemini API call."""
        self.calls_total += 1
        self.tokens_input_total += input_tokens
        self.tokens_output_total += output_tokens
        self.cost_total += cost
        self.latencies.append(latency_ms)

        logging.info(f"Gemini {operation}: {latency_ms}ms, "
                    f"${cost:.4f}, {input_tokens}in/{output_tokens}out")

    def log_failure(self, operation, error_code):
        """Track failed Gemini call."""
        self.calls_failed += 1
        logging.error(f"Gemini {operation} failed: {error_code}")

    def get_summary(self):
        """Daily summary for dashboard."""
        return {
            "calls_total": self.calls_total,
            "calls_failed": self.calls_failed,
            "success_rate": (self.calls_total - self.calls_failed) / max(self.calls_total, 1),
            "avg_latency_ms": sum(self.latencies) / len(self.latencies) if self.latencies else 0,
            "total_input_tokens": self.tokens_input_total,
            "total_output_tokens": self.tokens_output_total,
            "cost_today": self.cost_total,
        }
```

**Structured Output with JSON Schema (Production Standard):**

Gemini 3.0-Flash supports strict schema enforcement via `response_json_schema` parameter. This is CRITICAL for reliability:

```python
from pydantic import BaseModel, Field, validator
from typing import Literal
import json

class GeneratedQuestion(BaseModel):
    """Exam question with strict schema validation."""
    question_text: str = Field(..., description="Question text (max 500 chars)")
    option_a: str = Field(..., description="Option A (max 200 chars)")
    option_b: str = Field(..., description="Option B (max 200 chars)")
    option_c: str = Field(..., description="Option C (max 200 chars)")
    option_d: str = Field(..., description="Option D (max 200 chars)")
    correct_answer: Literal['A', 'B', 'C', 'D'] = Field(..., description="Correct answer must be A/B/C/D")
    explanation: str = Field(..., description="Explanation with source citation (max 500 chars)")
    difficulty: Literal['easy', 'medium', 'hard'] = Field(..., description="Question difficulty level")
    source_document_id: str = Field(..., description="Document ID from corpus")
    source_chunk_id: str = Field(..., description="Chunk ID from source")
    page_start: int = Field(..., ge=1, description="Page number (1-indexed)")
    page_end: int = Field(..., ge=1, description="End page if multi-page")
    citation_note: str = Field(..., min_length=1, description="Why this chunk sources this question")

    class Config:
        json_schema_extra = {
            "example": {
                "question_text": "What does TAS stand for?",
                "option_a": "TechFin Ancillary Services",
                "option_b": "Technology Advanced Systems",
                "option_c": "Transaction Authorization System",
                "option_d": "Technical Analysis Software",
                "correct_answer": "A",
                "explanation": "TAS = TechFin Ancillary Services Regulations 2025, per IFSCA circular dated March 2025.",
                "difficulty": "easy",
                "source_document_id": "doc_tas_regs_2025",
                "source_chunk_id": "chunk_tas_001",
                "page_start": 1,
                "page_end": 1,
                "citation_note": "From IFSCA TAS Regulations 2025 definitions section"
            }
        }

class EssayGradeResponse(BaseModel):
    """Essay grading with strict rubric validation."""
    content_accuracy: int = Field(..., ge=0, le=25, description="Content accuracy score (0-25)")
    structure_clarity: int = Field(..., ge=0, le=25, description="Structure and clarity (0-25)")
    regulatory_knowledge: int = Field(..., ge=0, le=25, description="Regulatory knowledge (0-25)")
    examples_evidence: int = Field(..., ge=0, le=25, description="Examples and evidence (0-25)")
    overall_score: int = Field(..., ge=0, le=100, description="Sum of four rubrics")
    strengths: list[str] = Field(..., max_items=5, description="Top 1-5 strengths")
    weaknesses: list[str] = Field(..., max_items=5, description="Top 1-5 weaknesses")
    suggested_sources: list[str] = Field(..., max_items=10, description="Chunk IDs for evidence")

    @validator('overall_score')
    def validate_total(cls, v, values):
        expected = values.get('content_accuracy', 0) + values.get('structure_clarity', 0) + \
                   values.get('regulatory_knowledge', 0) + values.get('examples_evidence', 0)
        assert v == expected, f"Overall score must equal sum of rubrics: {v} != {expected}"
        return v

# Usage with strict schema enforcement
class GeminiStructuredOutput:
    """Enforce strict schema in Gemini responses."""

    @staticmethod
    def generate_question_with_schema(topic_id, chunks):
        """Generate question with mandatory JSON schema compliance."""
        from google import genai
        from google.genai import types

        client = genai.Client()
        schema = GeneratedQuestion.model_json_schema()

        prompt = f"""
Generate 1 exam question exactly matching this JSON schema:

Topic: {topic_id}
Source context:
{chr(10).join(c['text'][:300] for c in chunks)}

CRITICAL REQUIREMENTS:
1. correct_answer MUST be exactly one of: A, B, C, D
2. difficulty MUST be exactly one of: easy, medium, hard
3. citation_note MUST cite the specific source text
4. Return ONLY valid JSON matching the schema (no markdown, no explanations)
"""

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema
            )
        )

        try:
            question_data = json.loads(response.text)
            question = GeneratedQuestion(**question_data)
            return question
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Schema validation failed: {e}\nResponse: {response.text}")
            return None

    @staticmethod
    def grade_essay_with_schema(essay_text, topic_id, source_chunks):
        """Grade essay with strict schema validation."""
        from google import genai
        from google.genai import types

        client = genai.Client()
        schema = EssayGradeResponse.model_json_schema()

        prompt = f"""
Grade this IFSCA essay using EXACTLY this 4-rubric schema.

Essay: {essay_text[:2000]}

Rubrics (0-25 each):
1. Content Accuracy: Factual correctness, no regulatory errors
2. Structure and Clarity: Coherent intro/body/conclusion
3. Regulatory Knowledge: IFSCA/GIFT ecosystem depth
4. Examples and Evidence: Data points, amendments, real examples

Return ONLY valid JSON matching schema (no markdown).
"""

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=schema
            )
        )

        try:
            grade_data = json.loads(response.text)
            grade = EssayGradeResponse(**grade_data)
            return grade
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Essay grade schema validation failed: {e}")
            return None
```

**Token Counting (BEFORE request - Critical for cost control):**

```python
from google import genai

class TokenCounter:
    """Count tokens BEFORE sending request to predict costs."""

    @staticmethod
    def count_tokens_before_request(prompt, model="gemini-3-flash-preview"):
        """
        Predict token usage before calling generate_content.

        Returns: {
            'input_tokens': N,
            'estimated_output_tokens': M,  # Estimated as ~20-30% of input
            'estimated_cost_usd': cost
        }
        """
        client = genai.Client()

        # Count input tokens (deterministic)
        token_count = client.models.count_tokens(
            model=model,
            contents=prompt
        )

        input_tokens = token_count.total_tokens
        # Estimate output as 25% of input (conservative)
        estimated_output = int(input_tokens * 0.25)
        total_estimated = input_tokens + estimated_output

        # Pricing: $0.075 per 1M tokens (Gemini 3.0 Flash)
        cost_per_token = 0.075 / 1_000_000
        estimated_cost = total_estimated * cost_per_token

        return {
            'input_tokens': input_tokens,
            'estimated_output_tokens': estimated_output,
            'estimated_total_tokens': total_estimated,
            'estimated_cost_usd': estimated_cost
        }

    @staticmethod
    def capture_actual_usage(response):
        """Extract actual token usage from response."""
        metadata = response.usage_metadata

        return {
            'input_tokens': metadata.prompt_token_count,
            'output_tokens': metadata.candidates_token_count,
            'cached_tokens': metadata.cached_content_token_count or 0,
            'thinking_tokens': metadata.thoughts_token_count or 0,
            'total_tokens': metadata.total_token_count,
            'cost_usd': (metadata.total_token_count * 0.075 / 1_000_000)
        }

# Usage pattern
def generate_question_with_cost_tracking(topic_id, chunks):
    """Generate question with token cost prediction and tracking."""

    # 1. PREDICT cost before requesting
    prompt = build_question_prompt(topic_id, chunks)
    prediction = TokenCounter.count_tokens_before_request(prompt)

    if prediction['estimated_cost_usd'] > 0.005:  # Threshold: $0.005 per question
        logging.warning(f"High-cost question generation: ${prediction['estimated_cost_usd']:.6f}")

    # 2. EXECUTE request
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=GeneratedQuestion.model_json_schema()
        )
    )

    # 3. CAPTURE actual usage
    actual = TokenCounter.capture_actual_usage(response)
    cost_tracker.log_api_call('question_generation', actual['input_tokens'], actual['output_tokens'], actual['cost_usd'])

    return response, actual
```

**Safety Settings (Prevent harmful content generation):**

```python
from google import genai
from google.genai import types

class SafetySettingsForExamPrep:
    """Configure safety filters for exam prep context."""

    # IFSCA exam prep is low-risk; relaxed filtering appropriate
    STANDARD_SETTINGS = [
        types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="BLOCK_LOW_AND_ABOVE"  # Block all hate speech
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="BLOCK_MEDIUM_AND_ABOVE"  # Exam context: no sexual content expected
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="BLOCK_LOW_AND_ABOVE"  # Block dangerous (e.g., weapons)
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="BLOCK_HIGH_AND_ABOVE"  # Allow critical analysis, block personal attacks
        ),
    ]

    @staticmethod
    def apply_safety_settings(client_call):
        """Add safety settings to any Gemini call."""
        return client_call.copy(
            config=types.GenerateContentConfig(
                safety_settings=SafetySettingsForExamPrep.STANDARD_SETTINGS
            )
        )

# Usage
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=prompt,
    config=types.GenerateContentConfig(
        safety_settings=SafetySettingsForExamPrep.STANDARD_SETTINGS,
        response_json_schema=GeneratedQuestion.model_json_schema()
    )
)

# Check if content was blocked
if response.candidates[0].finish_reason == "SAFETY":
    logging.warning("Response blocked by safety filter")
    logging.info(f"Safety ratings: {response.candidates[0].safety_ratings}")
```

---

### Layer 5: API Layer

Responsibilities:

- Serve frontend.
- Persist attempts and history.
- Expose source search.
- Generate mocks and drills via Gemini 3.0-Flash.
- Grade essays via Gemini 3.0-Flash.
- Track amendments with AI extraction.
- Return analytics.
- Manage Gemini key rotation and error handling.

**Gemini Integration Points:**

- `POST /api/generate-smart-mock` → Uses Gemini 3.0-Flash streaming
- `POST /api/penalty-drill` → Uses Gemini 3.0-Flash streaming
- `POST /api/grade-essay` → Uses Gemini 3.0-Flash with context caching
- `POST /api/record-amendment` → Calls Gemini for question generation + topic extraction
- Background batch job → Uses Gemini Batch API for bulk question seeding

**SSE (Server-Sent Events) Stream Management:**

Stream lifecycle for all real-time operations:

```python
from fastapi.responses import StreamingResponse
from fastapi import APIRouter
import asyncio
import json

router = APIRouter()

@router.get("/api/stream/smart-mock/{mock_id}")
async def stream_smart_mock(mock_id: str):
    """
    SSE stream for progressive mock question generation.

    Events:
    - stream:start {total_questions: 50}
    - stream:question {number: 1, question_id: "q1"}
    - stream:progress {current: 1, total: 50, percent: 2}
    - stream:complete {mock_id: "abc"}
    - stream:error {code: 500, message: "..."}
    """
    async def event_generator():
        try:
            # Emit start
            yield 'event: stream:start\ndata: {"total_questions": 50}\n\n'

            # Retrieve weak topics (cached, no AI)
            weak_topics = get_weak_topics_ranked(limit=10)

            # Allocate 60/25/15
            allocation = allocate_60_25_15(weak_topics, total_questions=50)

            # For each topic's allocation, generate questions
            question_count = 0
            for topic_id, num_questions in allocation.items():
                for i in range(num_questions):
                    try:
                        # Retrieve source chunks
                        chunks = search_chunks_by_topic(topic_id, limit=3)

                        # Call Gemini with streaming
                        stream_response = gemini_client.models.generate_content(
                            model="gemini-3-flash-preview",
                            contents=build_question_prompt(topic_id, chunks),
                            stream=True,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                        )

                        # Accumulate response
                        full_response = ""
                        for chunk in stream_response:
                            full_response += chunk.text

                        # Parse and validate
                        question_data = json.loads(full_response)
                        question = GeneratedQuestion(**question_data)

                        # Save to database
                        question_id = save_question(question)

                        # Emit question event
                        question_count += 1
                        yield f'event: stream:question\ndata: {json.dumps({
                            "number": question_count,
                            "question_id": question_id,
                            "topic": topic_id
                        })}\n\n'

                        # Emit progress
                        yield f'event: stream:progress\ndata: {json.dumps({
                            "current": question_count,
                            "total": 50,
                            "percent": int(100 * question_count / 50)
                        })}\n\n'

                    except Exception as e:
                        logging.error(f"Question generation failed: {e}")
                        yield f'event: stream:error\ndata: {json.dumps({
                            "code": 400,
                            "message": f"Question {question_count + 1} failed: {str(e)}"
                        })}\n\n'
                        continue

            # Final completion
            yield f'event: stream:complete\ndata: {json.dumps({
                "mock_id": mock_id,
                "total_questions_generated": question_count
            })}\n\n'

        except Exception as e:
            logging.error(f"Stream error: {e}")
            yield f'event: stream:error\ndata: {json.dumps({
                "code": 500,
                "message": str(e)
            })}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering if used
        }
    )

@router.post("/api/stream/essay-grade")
async def stream_essay_grade(essay_submission: EssaySubmissionRequest):
    """
    SSE stream for progressive essay grading with rubric feedback.

    Events:
    - grade:start {essay_id: "e1"}
    - grade:rubric_score {rubric: "content_accuracy", score: 22}
    - grade:feedback_start {rubric: "content_accuracy"}
    - grade:feedback_delta {text: "partial feedback..."}
    - grade:feedback_complete {rubric: "content_accuracy"}
    - grade:evidence {sources: ["chunk_1", "chunk_2"]}
    - grade:complete {overall_score: 86}
    """
    async def event_generator():
        try:
            essay_id = save_essay_draft(essay_submission)

            yield f'event: grade:start\ndata: {json.dumps({
                "essay_id": essay_id
            })}\n\n'

            # Retrieve source context
            topic_chunks = search_chunks_by_topic(
                essay_submission.topic,
                limit=10
            )

            # Build grading prompt with rubrics
            grading_prompt = f"""
Grade this IFSCA essay using the 4 rubrics. Return JSON with scores and feedback.

Essay text: {essay_submission.essay_text}

Topic: {essay_submission.topic}

Source context:
{format_chunks_for_prompt(topic_chunks)}

Rubrics (0-25 each):
1. Content Accuracy - Correct facts, relevant arguments, no errors
2. Structure and Clarity - Intro, flow, headings, conclusion, coherence
3. Regulatory Knowledge - IFSCA/GIFT/sector depth and correct usage
4. Examples and Evidence - Official data, amendments, sector examples

Return JSON:
{{
  "content_accuracy": <0-25>,
  "structure_clarity": <0-25>,
  "regulatory_knowledge": <0-25>,
  "examples_evidence": <0-25>,
  "feedback": {{
    "content_accuracy": "...",
    "structure_clarity": "...",
    "regulatory_knowledge": "...",
    "examples_evidence": "..."
  }},
  "suggested_sources": ["chunk_id_1", "chunk_id_2"]
}}
"""

            # Stream grading from Gemini
            stream_response = gemini_client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=grading_prompt,
                stream=True,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            # Accumulate response
            full_response = ""
            for chunk in stream_response:
                full_response += chunk.text

            # Parse
            grade_data = json.loads(full_response)
            grade_obj = EssayGradeResponse(**grade_data)

            # Emit rubric scores
            for rubric, score in [
                ("content_accuracy", grade_obj.content_accuracy),
                ("structure_clarity", grade_obj.structure_clarity),
                ("regulatory_knowledge", grade_obj.regulatory_knowledge),
                ("examples_evidence", grade_obj.examples_evidence)
            ]:
                yield f'event: grade:rubric_score\ndata: {json.dumps({
                    "rubric": rubric,
                    "score": score
                })}\n\n'
                await asyncio.sleep(0.1)  # Stagger events for UI effect

            # Emit feedback per rubric
            for rubric, feedback in grade_obj.feedback.items():
                yield f'event: grade:feedback_start\ndata: {json.dumps({
                    "rubric": rubric
                })}\n\n'

                # Stream feedback word by word
                for word in feedback.split():
                    yield f'event: grade:feedback_delta\ndata: {json.dumps({
                        "text": word + " "
                    })}\n\n'
                    await asyncio.sleep(0.05)

                yield f'event: grade:feedback_complete\ndata: {json.dumps({
                    "rubric": rubric
                })}\n\n'

            # Emit suggested sources
            yield f'event: grade:evidence\ndata: {json.dumps({
                "sources": grade_obj.suggested_sources
            })}\n\n'

            # Final score
            yield f'event: grade:complete\ndata: {json.dumps({
                "overall_score": grade_obj.overall_score,
                "essay_id": essay_id
            })}\n\n'

            # Save to database
            save_essay_grade(essay_id, grade_obj)

        except Exception as e:
            logging.error(f"Essay grading stream error: {e}")
            yield f'event: grade:error\ndata: {json.dumps({
                "message": str(e)
            })}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )
```

**Connection Resilience and Fallback:**

```python
class StreamConnectionManager:
    """Handles stream reconnection and fallback."""

    MAX_RETRIES = 3
    FALLBACK_TIMEOUT = 5000  # ms

    @staticmethod
    async def stream_with_fallback(stream_fn, fallback_fn, stream_name):
        """
        Attempt streaming; fall back to sync if stream fails.

        Args:
            stream_fn: Async generator for streaming response
            fallback_fn: Sync function returning full response
            stream_name: Stream identifier for logging
        """
        try:
            # Try streaming with timeout
            async with asyncio.timeout(30):
                async for event in stream_fn():
                    yield event
        except asyncio.TimeoutError:
            logging.warning(f"Stream {stream_name} timeout after 30s, using fallback")
            # Return fallback as non-streaming
            result = await fallback_fn()
            yield f'event: fallback\ndata: {json.dumps(result)}\n\n'
        except Exception as e:
            logging.error(f"Stream {stream_name} error: {e}, using fallback")
            result = await fallback_fn()
            yield f'event: fallback\ndata: {json.dumps(result)}\n\n'
```

**Advanced Error Handling with Specific Error Codes:**

```python
import time
from google.api_core import exceptions
import logging

class GeminiErrorHandler:
    """Handle specific Gemini API error codes with appropriate recovery."""

    # Error code definitions from Context7 documentation
    ERROR_CODES = {
        400: "Bad Request - Invalid parameter or schema",
        401: "Unauthorized - Invalid or expired API key",
        403: "Forbidden - Permission denied",
        429: "Rate Limited - Too many requests (retry with backoff)",
        500: "Internal Server Error - Transient issue (retry)",
        503: "Service Unavailable - Server overloaded (retry with long backoff)",
    }

    @staticmethod
    def handle_error_with_recovery(error, operation, retry_count=0, max_retries=3):
        """
        Handle specific error codes with appropriate recovery strategy.

        Returns: {
            'should_retry': bool,
            'delay_seconds': int,
            'fallback_action': str,
            'log_message': str
        }
        """
        error_code = getattr(error, 'code', None) or error.status_code

        if error_code == 429:  # Rate limited
            delay = min(60, 2 ** retry_count)  # Exponential backoff, max 60s
            return {
                'should_retry': retry_count < max_retries,
                'delay_seconds': delay,
                'fallback_action': 'switch_key',
                'log_message': f"Rate limited (429). Retry in {delay}s with next key."
            }

        elif error_code == 503:  # Service unavailable
            delay = min(300, 5 * (2 ** retry_count))  # Longer backoff for service unavailable
            return {
                'should_retry': retry_count < max_retries,
                'delay_seconds': delay,
                'fallback_action': 'queue_for_later',
                'log_message': f"Service unavailable (503). Retry in {delay}s."
            }

        elif error_code == 500:  # Internal server error (transient)
            delay = 2 ** retry_count
            return {
                'should_retry': retry_count < max_retries,
                'delay_seconds': delay,
                'fallback_action': 'retry_same_key',
                'log_message': f"Internal error (500). Retry in {delay}s."
            }

        elif error_code == 401:  # Unauthorized - key issue
            return {
                'should_retry': False,
                'delay_seconds': 0,
                'fallback_action': 'mark_key_invalid',
                'log_message': "Unauthorized (401). API key invalid or expired."
            }

        elif error_code == 400:  # Bad request - schema/prompt issue
            return {
                'should_retry': False,
                'delay_seconds': 0,
                'fallback_action': 'log_and_skip',
                'log_message': f"Bad request (400). Invalid schema or prompt."
            }

        elif isinstance(error, exceptions.DeadlineExceeded):  # Timeout
            return {
                'should_retry': retry_count < max_retries,
                'delay_seconds': 10,
                'fallback_action': 'use_cached',
                'log_message': "Request timeout. Using cached response if available."
            }

        else:  # Unknown error
            return {
                'should_retry': retry_count < 1,
                'delay_seconds': 5,
                'fallback_action': 'use_fallback',
                'log_message': f"Unknown error ({error_code}): {str(error)}"
            }

@staticmethod
async def call_gemini_with_recovery(operation_fn, operation_name, max_retries=3):
    """
    Call Gemini with full error recovery strategy.

    operation_fn: async function that calls Gemini
    operation_name: string like 'question_generation'
    """
    retry_count = 0

    while retry_count < max_retries:
        try:
            result = await operation_fn()
            return result

        except Exception as e:
            recovery = GeminiErrorHandler.handle_error_with_recovery(
                e, operation_name, retry_count, max_retries
            )

            logging.error(recovery['log_message'])

            if not recovery['should_retry']:
                if recovery['fallback_action'] == 'use_cached':
                    return get_cached_result(operation_name)
                elif recovery['fallback_action'] == 'mark_key_invalid':
                    gemini_key_manager.mark_unhealthy(current_key, "401_invalid")
                    raise
                else:
                    raise

            # Prepare for retry
            if recovery['fallback_action'] == 'switch_key':
                gemini_key_manager.mark_rate_limited(current_key)

            delay = recovery['delay_seconds']
            await asyncio.sleep(delay)
            retry_count += 1
```

**Timeout Configuration (Critical for long-running operations):**

```python
from google import genai
from google.genai import types

class TimeoutConfiguration:
    """Configure timeouts for different operation types."""

    # Default timeouts by operation type
    OPERATION_TIMEOUTS = {
        'question_generation': 30_000,  # 30 seconds (usually fast)
        'essay_grading': 60_000,  # 60 seconds (may analyze long essays)
        'amendment_extraction': 45_000,  # 45 seconds (document analysis)
        'batch_job_check': 10_000,  # 10 seconds (status checking)
        'cache_creation': 60_000,  # 60 seconds (document ingestion)
    }

    @staticmethod
    def get_timeout_for_operation(operation_name):
        """Get appropriate timeout (milliseconds) for operation."""
        return TimeoutConfiguration.OPERATION_TIMEOUTS.get(operation_name, 30_000)

    @staticmethod
    def call_with_timeout(operation_fn, operation_name, timeout_ms=None):
        """Call operation with global or per-operation timeout."""
        if timeout_ms is None:
            timeout_ms = TimeoutConfiguration.get_timeout_for_operation(operation_name)

        client = genai.Client(
            http_options=types.HttpOptions(timeout=timeout_ms)
        )

        try:
            result = operation_fn(client)
            return result
        except TimeoutError as e:
            logging.error(f"Operation {operation_name} exceeded timeout of {timeout_ms}ms")
            raise

# Usage with per-request timeout override
def generate_amendment_questions_with_timeout(amendment_id):
    """Generate amendment questions with longer timeout for batch ops."""
    amendment = get_amendment(amendment_id)

    def gen_fn(client):
        return client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=build_amendment_prompt(amendment)
        )

    # Override default timeout for this operation
    return TimeoutConfiguration.call_with_timeout(
        gen_fn,
        'amendment_extraction',
        timeout_ms=90_000  # 90 seconds for complex amendment analysis
    )
```

**File Upload API (Critical for corpus ingestion - 50MB PDF limit, 100MB general):**

```python
from google import genai
import os

class FileUploadManager:
    """
    Manage file uploads with proper size checking and resumable protocol.

    Size limits (CRITICAL):
    - General files: 100 MB (via standard upload)
    - PDF files: 50 MB (via resumable upload)
    - Audio/Video: 100 MB
    """

    UPLOAD_LIMITS = {
        'application/pdf': 50 * 1024 * 1024,  # 50 MB for PDFs
        'text/plain': 100 * 1024 * 1024,
        'application/json': 100 * 1024 * 1024,
        'audio/mpeg': 100 * 1024 * 1024,
        'video/mp4': 100 * 1024 * 1024,
        'default': 100 * 1024 * 1024,
    }

    FILE_STATE = {
        'PROCESSING': 'File is being processed (wait before using)',
        'ACTIVE': 'File ready for use in queries',
        'FAILED': 'File processing failed (retry upload)',
        'EXPIRED': 'File no longer available (re-upload required)',
    }

    @staticmethod
    def get_upload_limit_for_file(file_path):
        """Determine upload limit based on file type."""
        mime_type = FileUploadManager.get_mime_type(file_path)
        return FileUploadManager.UPLOAD_LIMITS.get(mime_type, FileUploadManager.UPLOAD_LIMITS['default'])

    @staticmethod
    def validate_file_for_upload(file_path):
        """Check file size against limits before uploading."""
        file_size = os.path.getsize(file_path)
        limit = FileUploadManager.get_upload_limit_for_file(file_path)

        if file_size > limit:
            raise ValueError(
                f"File {file_path} ({file_size} bytes) exceeds limit ({limit} bytes). "
                f"Use resumable upload or split file."
            )

        if file_size == 0:
            raise ValueError(f"File {file_path} is empty")

        logging.info(f"✓ File size OK: {file_size} bytes (limit: {limit} bytes)")

    @staticmethod
    async def upload_with_state_tracking(file_path):
        """
        Upload file and track state until ACTIVE.

        Returns file URI when ready, raises if fails.
        """
        client = genai.Client()

        # Validate before upload
        FileUploadManager.validate_file_for_upload(file_path)

        # Upload
        logging.info(f"Uploading {file_path}...")
        uploaded_file = client.files.upload(file=file_path)

        # Track state
        max_wait = 300  # 5 minutes max wait
        elapsed = 0
        check_interval = 2

        while elapsed < max_wait:
            file_info = client.files.get(name=uploaded_file.name)

            logging.info(f"File state: {file_info.state}")

            if file_info.state == 'ACTIVE':
                logging.info(f"✓ File ready: {file_info.uri}")
                return file_info

            elif file_info.state == 'FAILED':
                raise RuntimeError(f"File upload failed: {uploaded_file.name}")

            elif file_info.state == 'EXPIRED':
                raise RuntimeError(f"File upload expired: {uploaded_file.name}")

            # Still PROCESSING, wait and check again
            await asyncio.sleep(check_interval)
            elapsed += check_interval

        raise TimeoutError(f"File upload stuck in PROCESSING for {max_wait}s")

    @staticmethod
    def upload_large_pdf_resumable(file_path, display_name=None):
        """
        Upload large PDF using resumable protocol (handles network interruptions).

        For PDFs > 50MB (edge case), this ensures reliable transfer.
        """
        import requests

        file_size = os.path.getsize(file_path)
        mime_type = "application/pdf"

        # Step 1: Initiate resumable upload
        headers = {
            'X-Goog-Upload-Protocol': 'resumable',
            'X-Goog-Upload-Command': 'start',
            'X-Goog-Upload-Header-Content-Length': str(file_size),
            'X-Goog-Upload-Header-Content-Type': mime_type,
            'Content-Type': 'application/json',
        }

        body = {
            'file': {
                'display_name': display_name or os.path.basename(file_path)
            }
        }

        response = requests.post(
            f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={os.getenv('GEMINI_API_KEY')}",
            headers=headers,
            json=body
        )

        upload_url = response.headers.get('x-goog-upload-url')
        if not upload_url:
            raise RuntimeError(f"Failed to get upload URL: {response.text}")

        # Step 2: Upload file bytes
        with open(file_path, 'rb') as f:
            file_data = f.read()

        upload_headers = {
            'Content-Length': str(file_size),
            'X-Goog-Upload-Offset': '0',
            'X-Goog-Upload-Command': 'upload, finalize',
        }

        response = requests.post(
            upload_url,
            headers=upload_headers,
            data=file_data
        )

        file_info = response.json().get('file', {})
        logging.info(f"✓ Resumable upload complete: {file_info.get('uri')}")
        return file_info
```

---

---

## 9C. Production Deployment and Operations for Gemini 3.0-Flash

**Startup Validation Checklist:**

Before the app starts, verify Gemini setup:

```python
class GeminiStartupValidator:
    """Validate Gemini configuration at startup."""

    @staticmethod
    def validate_keys_present():
        """Require at least 5 API keys configured for resilience."""
        keys = [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 21)]
        active_keys = [k for k in keys if k]

        if len(active_keys) < 5:
            logging.error(f"FATAL: Only {len(active_keys)} keys configured (need minimum 5)")
            logging.error("Set GEMINI_API_KEY_1 through GEMINI_API_KEY_11+")
            raise ValueError(f"Need at least 5 API keys; got {len(active_keys)}")

        logging.info(f"✓ Initialized with {len(active_keys)} API keys (recommended: 11+)")

    @staticmethod
    def validate_key_connectivity():
        """Test each key with a lightweight API call."""
        keys = [os.getenv(f"GEMINI_API_KEY_{i}") for i in range(1, 21)]

        connectivity_ok = 0
        connectivity_failed = 0

        for i, key in enumerate(keys, 1):
            if not key:
                continue

            try:
                client = genai.Client(api_key=key)
                # Lightweight call: just check connectivity
                models = list(client.models.list())
                if models:
                    connectivity_ok += 1
                    logging.info(f"✓ Key {i:2d}: Connected")
                else:
                    connectivity_failed += 1
                    logging.warning(f"✗ Key {i:2d}: No models available")
            except Exception as e:
                connectivity_failed += 1
                logging.warning(f"✗ Key {i:2d}: {type(e).__name__}")

        if connectivity_ok < 5:
            raise RuntimeError(f"Only {connectivity_ok} keys healthy (need ≥5)")

        logging.info(f"✓ Gemini startup: {connectivity_ok} keys healthy, {connectivity_failed} unreachable")
        logging.info(f"✓ Total capacity: {connectivity_ok * 60} QPM, {connectivity_ok * 1500} RPD")

    @staticmethod
    def validate_model_available():
        """Verify gemini-3-flash-preview model is available."""
        try:
            # Try first healthy key
            for i in range(1, 21):
                key = os.getenv(f"GEMINI_API_KEY_{i}")
                if not key:
                    continue

                try:
                    client = genai.Client(api_key=key)
                    model_info = client.models.get("models/gemini-3-flash-preview")

                    if model_info:
                        logging.info(f"✓ Model available: gemini-3-flash-preview")
                        logging.info(f"  Input limit: {model_info.input_token_limit:,} tokens")
                        logging.info(f"  Output limit: {model_info.output_token_limit:,} tokens")
                        return True
                except:
                    continue

            logging.error("✗ Model check failed on all keys")
            return False

        except Exception as e:
            logging.error(f"Model check error: {e}")
            return False

    @staticmethod
    def validate_local_fallback_ready():
        """Ensure local mock mode is ready if Gemini fails."""
        logging.info("✓ Local fallback mode: Ready (activated if Gemini unavailable)")

# Usage in FastAPI startup:
@app.on_event("startup")
async def startup_event():
    try:
        GeminiStartupValidator.validate_keys_present()
        GeminiStartupValidator.validate_key_connectivity()
        GeminiStartupValidator.validate_model_available()
        GeminiStartupValidator.validate_local_fallback_ready()
        logging.info("\n" + "="*70)
        logging.info("✓✓✓ ALL GEMINI VALIDATIONS PASSED ✓✓✓")
        logging.info("="*70 + "\n")
    except Exception as e:
        logging.error(f"\n{'='*70}")
        logging.error(f"✗✗✗ GEMINI STARTUP FAILED ✗✗✗")
        logging.error(f"{e}")
        logging.error(f"{'='*70}\n")
        raise
```

**Logging and Monitoring:**

```python
import logging
from datetime import datetime

# Configure logging with Gemini context
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - [Gemini] - %(message)s',
    handlers=[
        logging.FileHandler("/logs/gemini_operations.log"),
        logging.StreamHandler()
    ]
)

class GeminiOperationsLog:
    """Centralized logging for all Gemini operations."""

    @staticmethod
    def log_question_generation(topic_id, difficulty, latency_ms, tokens_in, tokens_out, cost, success=True):
        status = "✓" if success else "✗"
        logging.info(
            f"{status} Question | Topic: {topic_id} | Diff: {difficulty} | "
            f"Latency: {latency_ms}ms | Tokens: {tokens_in}→{tokens_out} | Cost: ${cost:.4f}"
        )

    @staticmethod
    def log_essay_grading(essay_id, score, latency_ms, tokens_in, tokens_out, cost, success=True):
        status = "✓" if success else "✗"
        logging.info(
            f"{status} Essay Grade | ID: {essay_id} | Score: {score} | "
            f"Latency: {latency_ms}ms | Tokens: {tokens_in}→{tokens_out} | Cost: ${cost:.4f}"
        )

    @staticmethod
    def log_amendment_extraction(doc_id, amendments_found, latency_ms, cost, success=True):
        status = "✓" if success else "✗"
        logging.info(
            f"{status} Amendment Extract | Doc: {doc_id} | Found: {amendments_found} | "
            f"Latency: {latency_ms}ms | Cost: ${cost:.4f}"
        )

    @staticmethod
    def log_rate_limit_hit(key_id, retry_after_seconds):
        logging.warning(
            f"⚠ Rate Limit | Key {key_id} | Retry after {retry_after_seconds}s | "
            f"Switching to next key"
        )

    @staticmethod
    def log_api_error(operation, error_code, error_message, recovery_action):
        logging.error(
            f"✗ API Error | Operation: {operation} | Code: {error_code} | "
            f"Message: {error_message} | Recovery: {recovery_action}"
        )

    @staticmethod
    def log_daily_summary(total_calls, total_cost, success_rate):
        logging.info(
            f"\n{'='*70}\n"
            f"DAILY SUMMARY - Gemini Operations\n"
            f"Calls: {total_calls} | Cost: ${total_cost:.2f} | Success Rate: {success_rate}%\n"
            f"{'='*70}\n"
        )
```

**Cost Tracking and Budget Alerts:**

```python
class CostTracker:
    """Track Gemini API costs and alert if thresholds exceeded."""

    DAILY_BUDGET = 5.00  # $5 per day for exam prep
    WEEKLY_BUDGET = 30.00  # $30 per week
    MONTHLY_BUDGET = 75.00  # $75 for 12-week prep

    def __init__(self, db_path="costs.db"):
        self.db = sqlite3.connect(db_path)
        self.init_schema()

    def init_schema(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS gemini_costs (
                timestamp TEXT,
                operation TEXT,
                tokens_in INTEGER,
                tokens_out INTEGER,
                cost REAL,
                currency TEXT
            )
        """)
        self.db.commit()

    def log_api_call(self, operation, tokens_in, tokens_out, cost):
        """Log a single API call cost."""
        self.db.execute(
            "INSERT INTO gemini_costs VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), operation, tokens_in, tokens_out, cost, "USD")
        )
        self.db.commit()

        # Check thresholds
        self.check_daily_threshold()
        self.check_weekly_threshold()

    def get_today_cost(self):
        """Get total cost today."""
        today = datetime.now().strftime("%Y-%m-%d")
        cursor = self.db.execute(
            "SELECT SUM(cost) FROM gemini_costs WHERE DATE(timestamp) = ?",
            (today,)
        )
        result = cursor.fetchone()[0]
        return result or 0.0

    def get_this_week_cost(self):
        """Get total cost this week."""
        cursor = self.db.execute(
            """SELECT SUM(cost) FROM gemini_costs
               WHERE DATE(timestamp) >= DATE('now', '-7 days')"""
        )
        result = cursor.fetchone()[0]
        return result or 0.0

    def check_daily_threshold(self):
        """Alert if daily cost exceeds budget."""
        today_cost = self.get_today_cost()
        if today_cost > self.DAILY_BUDGET:
            logging.warning(
                f"⚠ DAILY BUDGET ALERT: ${today_cost:.2f} spent (limit: ${self.DAILY_BUDGET})"
            )

    def get_cost_by_operation(self):
        """Breakdown costs by operation type."""
        cursor = self.db.execute(
            "SELECT operation, SUM(cost), COUNT(*) FROM gemini_costs GROUP BY operation"
        )
        return cursor.fetchall()

    def export_cost_report(self, days=7):
        """Generate cost report for dashboard."""
        cursor = self.db.execute(
            """SELECT DATE(timestamp), SUM(cost), COUNT(*)
               FROM gemini_costs
               WHERE DATE(timestamp) >= DATE('now', ? || ' days')
               GROUP BY DATE(timestamp)""",
            (f"-{days}",)
        )
        return cursor.fetchall()
```

**Health Check Endpoint:**

```python
@app.get("/health/gemini")
async def health_check_gemini():
    """
    Detailed Gemini subsystem health check.

    Used by dashboard to show Gemini status and fallback activation.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "gemini_api": {
            "status": "healthy" if check_gemini_connectivity() else "down",
            "latency_ms": measure_gemini_latency(),
            "active_keys": count_active_keys(),
            "rate_limit_status": get_rate_limit_status()
        },
        "operations": {
            "questions_generated_today": count_questions_today(),
            "essays_graded_today": count_essays_graded_today(),
            "amendments_processed_today": count_amendments_today()
        },
        "costs": {
            "today": cost_tracker.get_today_cost(),
            "within_budget": cost_tracker.get_today_cost() < CostTracker.DAILY_BUDGET
        },
        "caching": {
            "active_caches": len(cache_manager.list_active_caches()),
            "cache_hit_rate": calculate_cache_hit_rate()
        }
    }
```

**Environment Configuration Template (11+ Keys):**

```bash
# .env file for Gemini configuration with 11+ key support

# API Keys (11 keys for maximum resilience and load distribution)
GEMINI_API_KEY_1=gsk_...
GEMINI_API_KEY_2=gsk_...
GEMINI_API_KEY_3=gsk_...
GEMINI_API_KEY_4=gsk_...
GEMINI_API_KEY_5=gsk_...
GEMINI_API_KEY_6=gsk_...
GEMINI_API_KEY_7=gsk_...
GEMINI_API_KEY_8=gsk_...
GEMINI_API_KEY_9=gsk_...
GEMINI_API_KEY_10=gsk_...
GEMINI_API_KEY_11=gsk_...

# Optional additional keys (up to 20 supported)
# GEMINI_API_KEY_12=gsk_...
# GEMINI_API_KEY_13=gsk_...
# ...

# Model selection
GEMINI_MODEL=gemini-3-flash-preview
GEMINI_USE_BATCH=true
GEMINI_USE_CACHING=true

# Rate limiting (per key)
# 11 keys × 60 QPM = 660 QPM total burst capacity
# 11 keys × 1500 RPD = 16,500 RPD total capacity
GEMINI_QPM_PER_KEY=60  # Free tier: 60 QPM per key
GEMINI_RPD_PER_KEY=1500  # Free tier: 1500 RPD per key
GEMINI_TOTAL_QPM=660  # 11 keys × 60
GEMINI_TOTAL_RPD=16500  # 11 keys × 1500
GEMINI_RETRY_ATTEMPTS=3
GEMINI_RETRY_BACKOFF_BASE=2

# Key rotation strategy
GEMINI_KEY_ROTATION_STRATEGY=least_used  # Options: round_robin, least_used, load_balanced
GEMINI_KEY_HEALTH_CHECK=true
GEMINI_KEY_ERROR_THRESHOLD=0.10  # Mark unhealthy if 10% error rate

# Cost management
GEMINI_DAILY_BUDGET=5.00
GEMINI_WEEKLY_BUDGET=30.00
GEMINI_MONTHLY_BUDGET=75.00
GEMINI_COST_ALERT_ENABLED=true
GEMINI_COST_ALERT_THRESHOLD=0.80  # Alert at 80% of budget

# Streaming config
GEMINI_STREAM_TIMEOUT_SECONDS=30
GEMINI_STREAM_CHUNK_SIZE=100
GEMINI_STREAM_BUFFER_SIZE=1024

# Context caching
GEMINI_ENABLE_CACHING=true
GEMINI_CACHE_TTL_HOURS=1
GEMINI_MAX_CACHES=100  # Max concurrent caches

# Batch processing
GEMINI_BATCH_ENABLED=true
GEMINI_BATCH_COMPLETION_WINDOW=24h
GEMINI_BATCH_NIGHT_ONLY=true
GEMINI_BATCH_MAX_REQUESTS=10000

# Monitoring and logging
GEMINI_LOG_LEVEL=INFO
GEMINI_LOG_RETENTION_DAYS=30
GEMINI_METRICS_EXPORT=true
GEMINI_HEALTH_CHECK_INTERVAL_SECONDS=300

# Fallback and resilience
GEMINI_FALLBACK_MODE=local_mock  # Options: local_mock, cached_only, limited
GEMINI_FALLBACK_ENABLED=true
```

**Capacity Planning with 11+ Keys:**

```
Single Free API Key (1 key):
- 60 QPM (queries per minute)
- 1,500 RPD (requests per day)
- Exam prep needs: ~24 questions/day = 0.017 QPM
- Status: SUFFICIENT but zero redundancy

With 5 Keys:
- 300 QPM burst
- 7,500 RPD total
- Resilience: If 1 key fails, 4 remain (80% capacity)
- Status: Good for exam prep

With 11 Keys (YOUR SETUP):
- 660 QPM burst capacity
- 16,500 RPD total capacity
- Resilience: If 3 keys fail, 8 remain (73% capacity)
- Multiple simultaneous bulk operations possible
- Status: EXCELLENT - can handle spikes and failures gracefully

With 11 Keys + 2 Concurrent Batches:
- Day 1: Seed 500 questions via Batch (free tier)
- Day 2: Seed 500 more questions via Batch (free tier)
- Real-time: Still 660 QPM available for mocks/essays
- Status: PRODUCTION-GRADE RESILIENCE
```

**Key Monitoring Dashboard (FastAPI endpoint):**

```python
@app.get("/api/admin/gemini-keys-status")
async def gemini_keys_status():
    """
    Real-time Gemini key health and distribution dashboard.
    Shows usage per key, error rates, rate limit status.
    """
    health = gemini_key_manager.get_health_status()
    distribution = gemini_key_manager.get_load_distribution()

    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_keys": health["total_keys"],
            "available_keys": health["available_keys"],
            "healthy_keys": health["healthy_keys"],
            "rate_limited_keys": health["rate_limited_keys"],
            "capacity_utilization": {
                "available_capacity_percent": 100 * health["available_keys"] / health["total_keys"]
            }
        },
        "key_details": health["keys"],
        "load_distribution": distribution["distribution"],
        "recommendations": [
            "All 11 keys healthy" if health["healthy_keys"] == 11 else f"⚠ {11 - health['healthy_keys']} keys unhealthy",
            "Load evenly distributed" if max(d["percent"] for d in distribution["distribution"].values()) < 15 else "⚠ Load imbalanced",
            "No rate limiting detected" if health["rate_limited_keys"] == 0 else f"⚠ {health['rate_limited_keys']} keys rate-limited"
        ]
    }
```

---

## 9D. Maximum Depth Gemini Implementation Details from Context7

**Complete Pricing Breakdown (Gemini 3.0 Flash):**

```
Input pricing:   $0.075 per 1M tokens (standard or batch)
Output pricing:  $0.075 per 1M tokens (standard) + $1.50 per 1M (batch output)
Cached input:    $0.01875 per 1M tokens (75% discount, 1M token = 15 min cache)
Cached read:     $0.01875 per 1M cached tokens

With caching enabled:
- First use of document: $0.075/1M (full price)
- Next 59 minutes: $0.01875/1M (75% discount on cached reads)
- Cache costs per hour: ~$0.075 creation + $0.01875 * 60 (queries) = maximum $1.20/hour

For exam prep corpus (let's say 500K average context):
- Create cache: 500K * $0.075 / 1M = $0.0375 (3.75 cents)
- Per query: 100K new tokens * $0.075 / 1M = $0.0075 (0.75 cents)
- With cache: 100K tokens * $0.01875 / 1M = $0.001875 (0.19 cents)
- Savings per query: 0.75 - 0.19 = 0.56 cents per query

ROI: Cache pays for itself after ~67 queries on same document
```

**System Instructions (Best Practices):**

```python
from google import genai
from google.genai import types

class SystemInstructionHandler:
    """Craft effective system instructions for exam prep."""

    QUESTION_GENERATION_INSTRUCTION = """You are an IFSCA exam expert. Generate multiple-choice questions that:
1. Are rigorous and appropriate for Grade A certification level
2. Test regulatory knowledge, not trivia
3. Include exactly ONE correct answer (A/B/C/D)
4. Have plausible but incorrect distractors
5. Always cite the source document in the explanation
6. Use official terminology from IFSCA regulations

Output ONLY valid JSON matching the provided schema. Do NOT include markdown, explanations, or commentary."""

    ESSAY_GRADING_INSTRUCTION = """You are an IFSCA essay evaluator. Grade essays on:
1. Content Accuracy (0-25): Regulatory facts, no errors
2. Structure & Clarity (0-25): Clear intro, body, conclusion
3. Regulatory Knowledge (0-25): Deep IFSCA/GIFT ecosystem understanding
4. Examples & Evidence (0-25): Real amendments, data points, sector examples

For weaknesses, identify SPECIFIC areas to improve.
For strengths, cite SPECIFIC examples from essay.
For sources, recommend EXACT chapters/sections to cite.

Output ONLY valid JSON matching the provided schema."""

    AMENDMENT_EXTRACTION_INSTRUCTION = """You are a regulatory change analyst for IFSCA. Extract amendments by identifying:
1. Which regulation is being changed
2. What was the old requirement/value
3. What is the new requirement/value
4. When does it take effect
5. Which exam topics are affected
6. How likely it is to appear on exam (high/medium/low)

Be precise about effective dates (YYYY-MM-DD). Use exact regulation names.
Output ONLY valid JSON. No commentary."""

    @staticmethod
    def apply_system_instruction(operation_type):
        """Get appropriate system instruction for operation."""
        instructions = {
            'question_generation': SystemInstructionHandler.QUESTION_GENERATION_INSTRUCTION,
            'essay_grading': SystemInstructionHandler.ESSAY_GRADING_INSTRUCTION,
            'amendment_extraction': SystemInstructionHandler.AMENDMENT_EXTRACTION_INSTRUCTION,
        }
        return instructions.get(operation_type, "")

    @staticmethod
    def call_with_system_instruction(model_call_fn, operation_type):
        """Wrap any Gemini call with system instruction."""
        instruction = SystemInstructionHandler.apply_system_instruction(operation_type)

        return model_call_fn(
            system_instruction=instruction
        )

# Usage
response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents=prompt,
    config=types.GenerateContentConfig(
        system_instruction=SystemInstructionHandler.QUESTION_GENERATION_INSTRUCTION,
        response_json_schema=GeneratedQuestion.model_json_schema()
    )
)
```

**Vision Capabilities for PDF/Image Processing:**

```python
import base64
from PIL import Image
import io

class VisionCapabilities:
    """Use Gemini vision for PDF/image analysis in exam prep."""

    @staticmethod
    async def extract_text_from_image(image_path):
        """
        OCR: Convert scanned PDF page or image to text.

        Use when source PDFs are low-quality scans.
        """
        client = genai.Client()

        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_data
                    }
                },
                {
                    "text": "Extract all text from this image precisely, preserving structure. Return as plain text."
                }
            ]
        )

        return response.text

    @staticmethod
    async def analyze_chart_for_question(chart_image_path):
        """
        Analyze regulatory chart/diagram and generate questions.

        Use for IFSCA organizational structure, fund classification trees, etc.
        """
        client = genai.Client()

        with open(chart_image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        prompt = """Analyze this regulatory chart/diagram and:
1. Describe its structure and relationships
2. Identify key entities and their roles
3. Extract 3 exam-level questions from the information shown

Return ONLY JSON:
{
  "description": "...",
  "key_entities": [...],
  "questions": [
    {"question": "...", "answer": "..."},
    ...
  ]
}"""

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_data
                    }
                },
                {"text": prompt}
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        return json.loads(response.text)

    @staticmethod
    async def generate_question_from_exam_screenshot(screenshot_path):
        """
        Create a question based on actual exam paper image.

        Use for PYQ analysis and similar question generation.
        """
        client = genai.Client()

        with open(screenshot_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_data
                    }
                },
                {
                    "text": """This is a question from an IFSCA exam paper.
Generate 2 similar questions testing the same concept but with different context.

Return JSON:
{
  "similar_questions": [
    {"question": "...", "option_a": "...", "option_b": "...", "option_c": "...", "option_d": "...", "correct_answer": "..."},
    ...
  ]
}"""
                }
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        return json.loads(response.text)
```

**Multi-Turn Conversations with Interactions API:**

```python
class InteractionsAPI:
    """Use Interactions API for multi-turn amendment discussions."""

    @staticmethod
    async def discuss_amendment_in_depth(amendment_id):
        """
        Multi-turn conversation about amendment details.

        Enables back-and-forth Q&A rather than single-shot generation.
        """
        client = genai.Client()
        amendment = get_amendment(amendment_id)

        # Turn 1: Initial analysis
        interaction_1 = await client.interactions.create(
            model="gemini-3-flash-preview",
            input=f"""Analyze this IFSCA amendment in detail:

Regulation: {amendment['regulation_name']}
Old value: {amendment['old_value']}
New value: {amendment['new_value']}
Effective: {amendment['effective_date']}

Provide:
1. Impact summary
2. Which entities are affected
3. Compliance deadline
4. Related regulations that changed
""",
            stream=False
        )

        initial_response = interaction_1.outputs[0].text

        # Turn 2: Follow-up for exam relevance
        interaction_2 = await client.interactions.create(
            model="gemini-3-flash-preview",
            input="Based on this amendment, what are the top 3 exam-level questions?",
            previous_interaction_id=interaction_1.id
        )

        exam_questions = interaction_2.outputs[0].text

        # Turn 3: Generate practice questions
        interaction_3 = await client.interactions.create(
            model="gemini-3-flash-preview",
            input="""Generate 5 multiple-choice questions testing this amendment.
Return JSON array with: question_text, options (A/B/C/D), correct_answer.""",
            previous_interaction_id=interaction_2.id
        )

        questions = json.loads(interaction_3.outputs[0].text)

        return {
            'amendment_id': amendment_id,
            'initial_analysis': initial_response,
            'exam_relevance': exam_questions,
            'practice_questions': questions,
            'conversation_id': interaction_3.id  # Save for future reference
        }
```

**Complete Cost Tracking with Token Predictions:**

```python
class ComprehensiveCostTracker:
    """Track all costs with predictions vs actual."""

    def __init__(self):
        self.predictions = []  # {operation, predicted, actual, variance}
        self.daily_costs = {}  # {date: {operation: cost}}

    def predict_operation_cost(self, operation_type, content_size_chars, model="gemini-3-flash-preview"):
        """Estimate cost for operation before executing."""
        # Rough token estimate: 1 token ≈ 4 characters
        estimated_tokens = content_size_chars / 4
        input_cost = (estimated_tokens * 0.075) / 1_000_000

        # Estimate output (25% of input)
        output_tokens = estimated_tokens * 0.25
        output_cost = (output_tokens * 0.075) / 1_000_000

        total_cost = input_cost + output_cost

        return {
            'operation': operation_type,
            'estimated_tokens': estimated_tokens,
            'estimated_input_cost': input_cost,
            'estimated_output_cost': output_cost,
            'estimated_total_cost': total_cost
        }

    def record_operation(self, operation_type, actual_usage, actual_cost, predicted_cost=None):
        """Record actual operation cost and calculate variance."""
        today = datetime.now().strftime("%Y-%m-%d")

        if today not in self.daily_costs:
            self.daily_costs[today] = {}

        if operation_type not in self.daily_costs[today]:
            self.daily_costs[today][operation_type] = 0

        self.daily_costs[today][operation_type] += actual_cost

        # Calculate variance if prediction was made
        variance = 0
        if predicted_cost:
            variance = ((actual_cost - predicted_cost) / predicted_cost * 100) if predicted_cost > 0 else 0

        self.predictions.append({
            'operation': operation_type,
            'predicted_cost': predicted_cost,
            'actual_cost': actual_cost,
            'variance_percent': variance,
            'timestamp': datetime.now().isoformat()
        })

    def get_cost_accuracy_metrics(self):
        """Analyze prediction accuracy over time."""
        if not self.predictions:
            return None

        variances = [p['variance_percent'] for p in self.predictions]
        return {
            'total_predictions': len(self.predictions),
            'avg_variance_percent': sum(variances) / len(variances),
            'max_variance_percent': max(variances),
            'min_variance_percent': min(variances),
            'predictions_within_10_percent': sum(1 for v in variances if abs(v) <= 10)
        }

    def export_daily_report(self, date_str=None):
        """Export daily cost breakdown by operation."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        daily = self.daily_costs.get(date_str, {})
        total_daily = sum(daily.values())

        return {
            'date': date_str,
            'by_operation': daily,
            'total_cost': total_daily,
            'prediction_accuracy': self.get_cost_accuracy_metrics()
        }
```

---

Traditional webhooks are pull-based POST callbacks to your server. Gemini's streaming is push-based Server-Sent Events (SSE), which is **actually better for exam prep** because:

1. Real-time progressive responses to the UI (no loading spinner)
2. Bandwidth-efficient (sends only deltas, not full responses)
3. Built-in error/completion events
4. Native browser support (EventSource API)

**Streaming Architecture for IFSCA Exam Prep:**

### Use Case 1: Real-Time Dashboard Recommendations

```
Timeline:
0ms   → User opens Dashboard
5ms   → Backend queries topic stats (fast, no AI)
10ms  → Backend fetches anomalies (weak topics, amendments due)
50ms  → Dashboard renders static stats

100ms → Dashboard initiates SSE stream for AI recommendation
        POST /api/dashboard-recommendation-stream

200ms → Gemini processes "What should this user do next?"
300ms → Event: recommendation.start
400ms → Event: recommendation.delta (data: "Take a...")
500ms → Event: recommendation.delta (data: " penalty drill...")
600ms → Event: recommendation.delta (data: " on Fund Management")
700ms → Event: recommendation.complete
800ms → UI updates with bold recommendation box
```

**Frontend code:**

```javascript
const eventSource = new EventSource('/api/dashboard-recommendation-stream');

eventSource.addEventListener('recommendation.start', (e) => {
  console.log('Recommendation streaming...');
  document.getElementById('recommendation-box').innerHTML = '';
});

eventSource.addEventListener('recommendation.delta', (e) => {
  const data = JSON.parse(e.data);
  document.getElementById('recommendation-box').innerHTML += data.text;
});

eventSource.addEventListener('recommendation.complete', (e) => {
  eventSource.close();
});

eventSource.onerror = (error) => {
  console.error('Stream error:', error);
  eventSource.close();
};
```

**Backend code (Python FastAPI):**

```python
@router.get("/api/dashboard-recommendation-stream")
async def dashboard_recommendation_stream():
    async def event_generator():
        yield 'event: recommendation.start\ndata: {}\n\n'

        # Get topic stats and anomalies
        weak_topics = ranks_topics_by_weakness()
        amendments_due = get_due_amendments()

        # Build prompt for Gemini with context
        prompt = f"User's weak topics: {weak_topics}. Amendments due: {amendments_due}. Generate a single-line recommendation for next 30 minutes of study."

        # Stream from Gemini with SSE
        stream = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            stream=True
        )

        recommendation_text = ""
        for chunk in stream:
            if chunk.text:
                recommendation_text += chunk.text
                yield f'event: recommendation.delta\ndata: {{"text": "{chunk.text}"}}\n\n'

        yield f'event: recommendation.complete\ndata: {{"full_text": "{recommendation_text}"}}\n\n'

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Use Case 2: Smart Mock Question Generation (Progressive)

```
Timeline:
0ms   → User clicks "Generate Smart Mock"
100ms → Backend allocates 60% weak / 25% medium / 15% strong
200ms → Backend retrieves chunks relevant to weak topics
300ms → Dashboard opens "Generating..." modal with progress bar

500ms → SSE stream begins: POST /api/smart-mock-stream
        Event: mock.start {mock_id: "abc123", total: 50}

600ms → For each of 50 questions:
        Event: mock.question_start {number: 1}
        Event: mock.question_update {text: "Which regulatory..."}
        Event: mock.question_delta {options: [...]}
        Event: mock.question_complete {question_id: "q1", saved: true}

3000ms → After 50 questions:
         Event: mock.complete {mock_id: "abc123"}

3100ms → UI redirect to exam mode or review
```

**Frontend progress display:**

```javascript
const mockStream = new EventSource('/api/smart-mock-stream');

mockStream.addEventListener('mock.start', (e) => {
  const data = JSON.parse(e.data);
  setProgress({ current: 0, total: data.total });
  setMockId(data.mock_id);
});

mockStream.addEventListener('mock.question_update', (e) => {
  const data = JSON.parse(e.data);
  setCurrentQuestion((prev) => ({
    ...prev,
    text: data.text
  }));
});

mockStream.addEventListener('mock.question_complete', (e) => {
  const data = JSON.parse(e.data);
  setProgress((prev) => ({
    ...prev,
    current: prev.current + 1
  }));
  updateMockPreview(data.question_id);
});

mockStream.addEventListener('mock.complete', (e) => {
  setProgress({ complete: true });
  setTimeout(() => redirectToExamMode(mockId), 1000);
});
```

### Use Case 3: Essay Grading with Real-Time Feedback

```
Timeline:
0ms   → User submits essay
100ms → Backend computes word count, structure metrics
200ms → Backend retrieves source chunks (TechFin, KYC, etc.)
300ms → SSE stream begins: POST /api/essay-grade-stream

400ms → Event: essay.start {essay_id: "e1"}
500ms → Gemini processes rubric grading
600ms → Event: essay.rubric_delta {rubric: "content_accuracy", score: 22}
700ms → Event: essay.rubric_delta {rubric: "structure_clarity", score: 23}
800ms → Event: essay.rubric_delta {rubric: "regulatory_knowledge", score: 20}
900ms → Event: essay.rubric_delta {rubric: "examples_evidence", score: 21}
1000ms → Event: essay.feedback_start {feedback_on: "content_accuracy"}
1100ms → Event: essay.feedback_delta {text: "Your explanation of..."}
1200ms → Event: essay.feedback_delta {text: " TAS framework is..."}
1300ms → Event: essay.feedback_delta {text: " mostly accurate..."}
1400ms → Event: essay.feedback_complete
1500ms → Event: essay.suggestions {evidence: ["chunk_1", "chunk_2"]}
1600ms → Event: essay.complete {overall_score: 86}

UI shows rubrics filling up, then feedback appearing progressively
```

**No Traditional Webhooks Needed:**

The streaming model is actually superior for exam prep because:

1. **User feedback is immediate** - No polling, no waiting
2. **Bandwidth minimal** - Only deltas streamed, not entire responses
3. **Backpressure built-in** - Client can pause/resume stream
4. **UI feels fast** - Progressive rendering instead of all-or-nothing
5. **No external IP exposure** - No need to expose webhook endpoints
6. **Gemini handles routing** - No need to manage callback URLs

**When to Use Each Streaming Pattern:**

| Pattern | Usage | Example |
|---------|-------|---------|
| SSE (HTTP streaming) | Real-time UI updates | Dashboard recommendation, mock generation, essay grading |
| WebSocket (bidirectional) | Interactive conversational | Future: Live amendment Q&A chatbot |
| Batch API | Bulk overnight processing | Generate 1000 practice questions in one job |
| Context Caching | Repeated queries on same docs | Bill all amendment queries as if they hit cache |

**SSE Implementation Checklist:**

- ✅ Django/FastAPI SSE route with `StreamingResponse`
- ✅ Event generator function that yields `event: name\ndata: json\n\n`
- ✅ Proper MIME type: `text/event-stream`
- ✅ Client-side `EventSource` listener
- ✅ Error handler (reconnect or fallback)
- ✅ Timeout after 30s if no events
- ✅ Progress bar UI for long operations
- ✅ Storage of stream results to database once complete

---

## 9B. Proposed Database Schema Extension

Do not replace current tables immediately. Extend carefully with migrations.

### `documents`

Fields:

- `document_id` text primary key.
- `title` text.
- `category` text.
- `source_type` text.
- `source_url` text.
- `local_pdf_path` text.
- `local_text_path` text.
- `sha256` text unique.
- `pages` integer.
- `line_count` integer.
- `publication_date` text.
- `downloaded_at` text.
- `ingested_at` text.
- `status` text.
- `notes` text.

### `document_chunks`

Fields:

- `chunk_id` text primary key.
- `document_id` text.
- `page_start` integer.
- `page_end` integer.
- `line_start` integer.
- `line_end` integer.
- `text` text.
- `token_estimate` integer.
- `chunk_hash` text.
- `created_at` text.

### `document_chunk_fts`

SQLite FTS5 table:

- `chunk_id`
- `document_id`
- `title`
- `text`
- `topic_tags`
- `source_type`

### `topics`

Fields:

- `topic_id` text primary key.
- `parent_topic_id` text.
- `phase` text.
- `paper` text.
- `display_name` text.
- `description` text.
- `base_weight` real.
- `exam_priority` integer.
- `is_amendment_sensitive` boolean.

### `chunk_topics`

Fields:

- `chunk_id` text.
- `topic_id` text.
- `confidence` real.
- `method` text.

### `amendment_events`

Fields:

- `amendment_id` text primary key.
- `title` text.
- `topic_id` text.
- `source_document_id` text.
- `source_chunk_id` text.
- `old_value` text.
- `new_value` text.
- `effective_date` text.
- `publication_date` text.
- `exam_priority` integer.
- `mastery_status` text.
- `questions_generated` integer.
- `last_reviewed_at` text.

This can coexist with the existing `amendments` table at first, then be merged.

### `questions`

Fields:

- `question_id` text primary key.
- `source` text.
- `topic_id` text.
- `subtopic_id` text.
- `question_text` text.
- `option_a` text.
- `option_b` text.
- `option_c` text.
- `option_d` text.
- `correct_answer` text.
- `explanation` text.
- `difficulty` text.
- `question_type` text.
- `is_amendment_based` boolean.
- `amendment_id` text.
- `created_by` text.
- `prompt_version` text.
- `verification_status` text.
- `created_at` text.

### `question_citations`

Fields:

- `question_id` text.
- `document_id` text.
- `chunk_id` text.
- `page_start` integer.
- `page_end` integer.
- `citation_note` text.

### `mock_sessions`

Fields:

- `mock_id` text primary key.
- `mock_type` text.
- `generated_at` text.
- `started_at` text.
- `submitted_at` text.
- `total_questions` integer.
- `score` real.
- `accuracy` real.
- `allocation_json` text.
- `difficulty_curve_json` text.
- `status` text.

### `mock_questions`

Fields:

- `mock_id` text.
- `question_id` text.
- `question_number` integer.
- `source_reason` text.

### `answers`

Fields:

- `answer_id` text primary key.
- `mock_id` text.
- `drill_id` text.
- `question_id` text.
- `selected_answer` text.
- `is_correct` boolean.
- `time_spent_seconds` integer.
- `marked_for_review` boolean.
- `answered_at` text.

### `essay_submissions`

Fields:

- `essay_id` text primary key.
- `prompt` text.
- `essay_text` text.
- `submitted_at` text.
- `time_limit_minutes` integer.
- `word_count` integer.
- `topic_tags` text.
- `overall_score` integer.

### `essay_scores`

Fields:

- `essay_id` text.
- `content_accuracy` integer.
- `structure_clarity` integer.
- `regulatory_knowledge` integer.
- `examples_evidence` integer.
- `feedback_json` text.
- `model_outline` text.
- `source_suggestions_json` text.

### `review_items`

Fields:

- `review_id` text primary key.
- `item_type` text.
- `item_id` text.
- `topic_id` text.
- `due_at` text.
- `interval_days` integer.
- `ease` real.
- `last_result` text.

### `recommendation_log`

Fields:

- `recommendation_id` text primary key.
- `created_at` text.
- `recommendation_type` text.
- `message` text.
- `reason_json` text.
- `accepted` boolean.
- `completed` boolean.

---

## 10. Topic Taxonomy

The app should use a deeper taxonomy than the current 13-topic list. The current IDs can remain as top-level buckets.

### Core Phase 2 / IFSCA Topics

1. `PH2_IFSCA_ACT`
   - IFSCA Act, 2019.
   - Authority structure.
   - Powers and functions.
   - Unified regulator concept.

2. `PH2_GIFT_IFSC`
   - GIFT City ecosystem.
   - IFSC purpose.
   - Entity types.
   - Global financial center positioning.

3. `PH2_FM_REGS`
   - Fund Management Regulations.
   - FME categories.
   - AIFs and schemes.
   - KMP/PPM/amendment issues.
   - ESG funds and fee waivers.

4. `PH2_BANKING`
   - IFSC Banking Units.
   - Banking Handbook.
   - Prudential norms.
   - Conduct of business.
   - Credit directions and module updates.

5. `PH2_CAPITAL`
   - Exchanges.
   - Depositories.
   - FPIs.
   - Capital market ecosystem.
   - NSE IFSC and India INX.

6. `PH2_CMI`
   - Capital Market Intermediaries Regulations.
   - Principal officer/compliance officer.
   - Certification.
   - Registration and obligations.

7. `PH2_LISTING`
   - Listing Regulations.
   - Direct listing.
   - SPACs.
   - ESG bonds.
   - SGrBs.
   - Transition bonds.
   - LEAP.

8. `PH2_PAYMENT`
   - Payment Services Regulations.
   - Payment service providers.
   - Regular/significant PSP concepts.
   - Payments Regulatory Board.

9. `PH2_TECHFIN_TAS`
   - TechFin and Ancillary Services Regulations 2025.
   - TAS transition circular.
   - TAS FAQs.
   - Sandbox and innovation framework.

10. `PH2_BULLION`
    - India International Bullion Exchange.
    - Qualified jewellers.
    - Authorized persons.
    - Vaulting and market access.

11. `PH2_INSURANCE`
    - IFSC Insurance Offices.
    - Reinsurance.
    - Insurance intermediaries.
    - IRDAI context where relevant.

12. `PH2_AIRCRAFT_SHIP_LEASING`
    - Aircraft leasing.
    - Ship leasing.
    - Tax and entity framework.
    - Asset finance structures.

13. `PH2_AML_KYC`
    - AML/CFT/KYC Guidelines.
    - KRA Regulations 2025.
    - NISM/IFSCA certification.
    - Beneficial ownership and onboarding.

14. `PH2_COMMODITY_TRADE`
    - Commodity trading hub.
    - Expert committee recommendations.
    - Global commodity trade via GIFT City.

15. `PH2_TAX`
    - IFSC tax benefits.
    - Income-tax holiday.
    - MAT.
    - GST/customs.
    - Specified funds.

16. `PH2_CURRENT_AFFAIRS`
    - Monthly current affairs.
    - Budget announcements.
    - Financial services policy.
    - International finance developments.

17. `PH2_MANAGEMENT_ORG`
    - Management syllabus areas.
    - Leadership, HR, communication, governance if applicable.

18. `PH2_ESSAY`
    - Essay-specific content themes.
    - Structure and examples.
    - Current examples and data points.

### Cross-cutting tags

Every chunk/question/amendment can also have:

- `STATIC`
- `AMENDMENT`
- `PYQ_PATTERN`
- `CURRENT_AFFAIRS`
- `DATA_POINT`
- `LEGAL_TEXT`
- `CONSULTING_CONTEXT`
- `ESSAY_EVIDENCE`
- `HIGH_YIELD`
- `LOW_CONFIDENCE`

---

## 11. Knowledge Ingestion Plan

### Step 1: Document registry

Create a script:

- `D:\Exam_preparation\backend\ingest_sources.py`

Responsibilities:

- Scan `source_documents`, `extracted_pdfs`, and known digest references.
- Identify PDFs and extracted text files.
- Compute SHA256.
- Insert or update `documents`.
- Mark duplicates.
- Record document category using path/name rules first.

### Step 2: Chunking

Chunk rules:

- Target 700-1,200 words per chunk for study material.
- Smaller chunks for regulations and FAQs.
- Preserve page and line references.
- Avoid splitting numbered regulations in the middle.
- Store chunk hash for dedupe.

### Step 3: FTS indexing

Populate:

- `document_chunks`
- `document_chunk_fts`

The current `knowledge_fts` table can either be migrated or kept as a compatibility layer.

### Step 4: Topic tagging

Initial deterministic tags:

- Filename keywords.
- Document category.
- Headings.
- Known phrases.

Examples:

- "Fund Management" -> `PH2_FM_REGS`.
- "Payment Services" -> `PH2_PAYMENT`.
- "TechFin" or "Ancillary Services" -> `PH2_TECHFIN_TAS`.
- "Bullion" or "IIBX" -> `PH2_BULLION`.
- "AML", "CFT", "KYC", "KRA" -> `PH2_AML_KYC`.
- "Listing", "SPAC", "SGrB", "Transition Bond" -> `PH2_LISTING`.

Later AI classification can refine tags, but deterministic tagging should come first.

### Step 5: Amendment extraction

Scan bulletins, ICSI Info Capsules, TAS docs, and official circulars for:

- Effective date.
- Publication date.
- Regulation name.
- Old/new value.
- Compliance deadline.
- Entity affected.
- Whether it is draft, final, consultation, FAQ, circular, or regulation.

### Step 6: Question seed generation

Generate seed questions only after citations exist.

Minimum seed target:

- 50 questions for IFSCA Act/GIFT basics.
- 75 questions for Fund Management.
- 75 questions for Banking.
- 75 questions for Capital Markets.
- 50 questions for Listing/Securities.
- 50 questions for Payment Services.
- 50 questions for TechFin/TAS.
- 40 questions for AML/KYC/KRA.
- 30 questions for Bullion/IIBX.
- 30 questions for Insurance.
- 30 questions for Aircraft/Ship Leasing.
- 50 questions for Current Affairs/Annual Report data.
- 45 questions from the first 15 critical amendments.

First milestone: 700 verified questions.

---

## 12. Smart Mock Algorithm

The current algorithm is a strong start. The final algorithm should be:

```
weakness_score =
    0.35 * historical_error_rate
  + 0.25 * recent_error_rate
  + 0.15 * low_attempt_confidence
  + 0.10 * exam_weight
  + 0.10 * amendment_recency
  + 0.05 * time_pressure_penalty
```

Where:

- `historical_error_rate`: all-time wrong percentage for topic.
- `recent_error_rate`: wrong percentage in recent attempts.
- `low_attempt_confidence`: boosts under-sampled topics without overreacting.
- `exam_weight`: topic importance from syllabus/PYQ/corpus.
- `amendment_recency`: recent regulatory change boost.
- `time_pressure_penalty`: high average time or unanswered questions.

Allocation:

- Tier 1 weak topics: 60 percent.
- Tier 2 medium topics: 25 percent.
- Tier 3 strong topics: 15 percent.

Difficulty:

- Weak topic with high exam weight: medium to hard, plus explanations.
- Weak topic with low attempts: easy to medium for calibration.
- Strong topic: medium/hard occasional traps.
- Amendment topic: recent application-style questions.

Must fix:

- The current code's docstring in `main.py` says 60/30/10 in one place while the desired final model is 60/25/15 and `database.py` implements 30/13/7. Standardize all docs and code to 60/25/15.
- Avoid reducing an allocation below zero during rounding correction.
- Add question selection from existing verified bank before asking Gemini to generate new questions.
- Save each smart mock's questions, not only metadata.

---

## 13. Penalty Drill Algorithm

Drill recommendation score:

```
drill_priority =
    0.40 * weakness_score
  + 0.20 * exam_weight
  + 0.15 * amendment_recency
  + 0.10 * days_since_last_review
  + 0.10 * repeated_error_flag
  + 0.05 * user_requested_boost
```

Drill types:

| Type | Trigger |
|---|---|
| Weakness drill | Topic accuracy below threshold |
| Amendment drill | New amendment or unmastered amendment |
| Replay drill | Wrong answers due for review |
| Speed drill | Accuracy is fine but time is high |
| Concept drill | Repeated errors in the same subtopic |
| Mixed drill | Final-stage consolidation |

Drill completion should update:

- Topic accuracy.
- Recent accuracy.
- Review queue.
- Weakness score.
- Dashboard recommendation.

---

## 14. Amendment Priority Algorithm

Amendment score:

```
amendment_priority =
    0.30 * recency
  + 0.25 * topic_exam_weight
  + 0.20 * source_authority
  + 0.10 * student_weakness_in_topic
  + 0.10 * compliance_deadline_nearness
  + 0.05 * cross-topic_relevance
```

Source authority ranking:

1. IFSCA official regulation/circular/gazette.
2. IFSCA bulletin/annual report.
3. ICSI study material or Info Capsule.
4. IndiaCode/bare act.
5. Professional firm report.
6. Coaching/PYQ/memory material.

Mastery states:

- `NEW`
- `QUESTIONS_GENERATED`
- `DRILLED_ONCE`
- `DRILLED_TWICE`
- `MASTERED`
- `STALE_NEEDS_REVIEW`

---

## 15. Essay Grading Plan

The essay lab needs a source-grounded grading flow:

1. User selects or receives an essay prompt.
2. User writes under timer.
3. System computes word count, structure markers, missing examples.
4. Retrieval finds relevant source chunks.
5. AI grades using the 4 rubrics.
6. AI returns JSON:
   - Scores.
   - Strengths.
   - Weaknesses.
   - Missing regulatory points.
   - Suggested source examples.
   - Improved outline.
   - Rewrite targets.
7. System stores the essay and score.
8. Dashboard updates essay trend.

Prompt types:

- Regulatory essay.
- GIFT City ecosystem essay.
- Financial services current affairs essay.
- Governance/compliance essay.
- Technology/fintech essay.
- International finance essay.
- Ethics/management essay.

Minimum essay bank:

- 20 regulatory essays.
- 20 current affairs essays.
- 15 GIFT City/business essays.
- 10 fintech/innovation essays.
- 10 governance/compliance essays.
- 10 management/leadership essays.

---

## 16. UI Plan

### Dashboard

Layout:

- Top strip: estimated readiness, total mocks, overall accuracy, essay average, amendment mastery.
- Left: topic heatmap.
- Center: recommended next action.
- Right: amendment alerts and review queue.
- Bottom: trends and recent sessions.

### Smart Mock

Controls:

- Generate Smart Mock.
- Choose question count: 25/50/75.
- Choose mode: balanced, weakness-heavy, amendment-heavy, PYQ-like.
- Show allocation before start.
- Start exam mode.

### Exam Mode

Interface:

- Timer top right.
- Question area.
- Options.
- Palette.
- Mark for review.
- Save and next.
- Clear response.
- Submit confirmation.

### Drill Lab

Controls:

- Topic dropdown.
- Difficulty selector.
- Drill type selector.
- Generate drill.
- Start drill.
- Review mistakes.

### Essay Lab

Controls:

- Prompt selector.
- Timer.
- Editor.
- Submit.
- Rubric score view.
- Feedback view.
- Suggested evidence panel.

### Amendment Tracker

Views:

- New amendments.
- Pending drills.
- Mastered amendments.
- Source references.
- Manual entry form.
- Auto-detection log.

### Knowledge Explorer

Purpose:

- Let the user search the corpus.
- Useful for audit and manual study.

Features:

- Search query.
- Filter by category/topic/date.
- Open chunk.
- Show source file.
- Generate questions from selected chunk.
- Add chunk to essay evidence bank.

---

## 17. API Roadmap

### Keep and harden existing endpoints

- `GET /health`
- `POST /api/upload-mock`
- `GET /api/weak-topics`
- `POST /api/penalty-drill`
- `POST /api/grade-essay`
- `POST /api/record-amendment`
- `POST /api/generate-smart-mock`
- `GET /api/dashboard`

### Add source and ingestion endpoints

- `POST /api/admin/ingest-documents`
- `GET /api/admin/ingestion-status`
- `GET /api/documents`
- `GET /api/documents/{document_id}`
- `GET /api/source-search?q=...`
- `GET /api/topics`
- `GET /api/topics/{topic_id}/sources`

### Add question endpoints

- `POST /api/questions/generate-from-source`
- `POST /api/questions/verify`
- `GET /api/questions`
- `GET /api/questions/{question_id}`

### Add mock lifecycle endpoints

- `POST /api/mocks/generate`
- `POST /api/mocks/{mock_id}/start`
- `POST /api/mocks/{mock_id}/answer`
- `POST /api/mocks/{mock_id}/submit`
- `GET /api/mocks/{mock_id}/review`

### Add drill lifecycle endpoints

- `POST /api/drills/generate`
- `POST /api/drills/{drill_id}/submit`
- `GET /api/drills/history`

### Add essay endpoints

- `GET /api/essays/prompts`
- `POST /api/essays/submit`
- `GET /api/essays/history`
- `GET /api/essays/{essay_id}`

### Add amendment endpoints

- `POST /api/amendments/seed`
- `POST /api/amendments/scan`
- `GET /api/amendments`
- `GET /api/amendments/pending-review`
- `POST /api/amendments/{amendment_id}/mark-mastered`

---

## 18. Implementation Roadmap

### Phase 0: Stabilize Existing Prototype

Goal:

- Remove inconsistencies and make the current app reliable before adding more.

Tasks:

- Consolidate duplicate `/api/dashboard` routes.
- Standardize smart mock allocation text to 60/25/15.
- Add no-key guard for Gemini setup.
- Add local development mock AI mode.
- Add basic tests for existing database functions.
- Confirm frontend calls match backend response shapes.
- Confirm upload mock format is documented and validated.

Exit criteria:

- Server starts cleanly.
- Dashboard returns one stable schema.
- Smart mock generation error is clear if Gemini keys are missing.
- Existing sample mock upload works.

### Phase 1: Source Vault and Corpus Ingestion

Goal:

- Make the 126 PDFs usable by the app.

Tasks:

- Add `documents`, `document_chunks`, and FTS tables.
- Build ingestion script.
- Ingest extracted text.
- Register source documents with categories.
- Add source search endpoint.
- Add Knowledge Explorer UI.

Exit criteria:

- At least 126 documents registered.
- At least 90 percent of extracted text chunks searchable.
- Search for "TechFin", "KRA", "Fund Management", "Payment Services", "Bullion", and "Transition Bonds" returns relevant chunks.

### Phase 2: Topic Mapping and High-Yield Index

Goal:

- Map corpus to exam topics.

Tasks:

- Create normalized topic table.
- Implement deterministic topic tagging.
- Run topic tagging across chunks.
- Store topic confidence.
- Add topic coverage dashboard.
- Identify low-coverage topics.

Exit criteria:

- Every major topic has source chunks.
- Topic heatmap can show source coverage.
- Question generation can retrieve topic-specific chunks.

### Phase 3: Amendment Seeding

Goal:

- Convert known 2024-2026 amendments into actionable study items.

Tasks:

- Seed the 15 critical amendments from research docs.
- Add additional amendments from ICSI capsules and bulletins.
- Link each amendment to source chunks.
- Generate 3-5 questions per amendment.
- Add amendment drill workflow.

Exit criteria:

- At least 15 critical amendments seeded.
- At least 45 amendment questions generated and cited.
- Dashboard shows drilled vs pending amendment status.

### Phase 4: Source-Grounded Question Factory

Goal:

- Generate and verify questions from sources.

Tasks:

- Build retrieval-before-generation pipeline.
- Add question JSON validation.
- Add citation requirement.
- Add generated question review queue.
- Add duplicate question detection.
- Seed first 700 verified questions.

Exit criteria:

- Generated questions include citations.
- Questions can be reviewed by source.
- Smart mocks can use stored question bank before calling Gemini.

### Phase 5: Full Mock Lifecycle

Goal:

- Turn smart mock generation into a complete attempt/review loop.

Tasks:

- Save generated mock questions.
- Add exam mode UI.
- Add answer submission.
- Add score calculation.
- Add review screen.
- Update topic stats after submission.
- Update spaced review queue.

Exit criteria:

- User can generate, take, submit, and review a 50-question mock end to end.
- Dashboard updates immediately after submission.

### Phase 6: Drill Engine Upgrade

Goal:

- Make drills adaptive and history-aware.

Tasks:

- Add drill session tables.
- Add wrong-answer replay.
- Add amendment drill.
- Add speed drill.
- Add source-cited explanations.
- Add mastery delta.

Exit criteria:

- Drill recommendation changes based on latest performance.
- Drill results update topic mastery and review queue.

### Phase 7: Essay Lab Upgrade

Goal:

- Build complete essay history and improvement loop.

Tasks:

- Add essay tables.
- Add prompt bank.
- Add timed editor.
- Add rubric storage.
- Add essay trends.
- Add source evidence suggestions.

Exit criteria:

- User can write an essay, get graded, review rubric feedback, and track improvement across attempts.

### Phase 8: Amendment Radar Automation

Goal:

- Reduce manual amendment tracking.

Tasks:

- Build source scanner for official sites where accessible.
- Add manual import fallback for WAF-blocked sources.
- Add file-drop watcher for new PDFs.
- Extract amendment candidates.
- Require user confirmation before accepting major new amendments.

Exit criteria:

- New local Info Capsule or bulletin can be ingested and candidate amendments extracted.
- Dashboard flags new unreviewed amendments.

### Phase 9: Analytics and Prediction

Goal:

- Make the dashboard genuinely decision-grade.

Tasks:

- Implement score trend.
- Implement topic trend.
- Implement essay trend.
- Implement amendment mastery trend.
- Implement readiness estimate with confidence band.
- Implement ROI by study time.

Exit criteria:

- Dashboard can explain every recommendation and score estimate.

### Phase 10: Polish and Deployment

Goal:

- Make the system comfortable for daily use.

Tasks:

- Improve UI density and responsiveness.
- Add local startup script.
- Add backup/export.
- Add settings page.
- Add test suite.
- Add documentation for daily workflow.

Exit criteria:

- User can run locally, study daily, and trust backups.

---

## 19. Testing Plan

### Unit tests

Must cover:

- `calculate_weakness_score`.
- `allocate_question_slots`.
- Rounding to exactly 50 questions.
- No negative allocation.
- Topic tagging rules.
- Amendment priority scoring.
- Essay score JSON validation.
- Ingestion dedupe.

### Integration tests

Must cover:

- Upload mock -> topic stats update.
- Generate smart mock -> questions saved.
- Submit mock -> accuracy updates.
- Record amendment -> questions generated.
- Source search -> relevant chunks returned.
- Essay submit -> scores stored.

### Golden tests

Create fixed test cases:

- One mock with known topic distribution.
- One amendment with known priority.
- One source chunk with expected topic tag.
- One essay with expected rubric shape.

### AI safety/quality tests

For generated questions:

- Must have four options.
- Must have one valid correct answer.
- Must include explanation.
- Must include citation.
- Must not ask outside topic.
- Must not contradict cited source.

For essays:

- Rubric totals must equal overall score.
- Feedback must mention concrete improvements.
- Source suggestions must map to corpus chunks.

---

## 20. Daily Study Workflow

Morning:

- Open dashboard.
- Review recommended next action.
- Generate smart mock or take scheduled drill.

Afternoon:

- Take a 50-question smart mock in exam mode.
- Submit and review errors.
- Add wrong answers to review queue automatically.

Evening:

- Complete one penalty drill.
- Write or revise one essay on scheduled days.
- Review pending amendments.

Weekly:

- Ingest any new PDFs/capsules.
- Run amendment scan.
- Take at least one full smart mock.
- Review analytics trend.
- Rebalance topic priorities if needed.

Final 2 weeks:

- Increase full mocks.
- Focus on weak high-yield topics.
- Drill all recent amendments twice.
- Write essays under timer.
- Use TCS-style exam mode only.

---

## 21. Success Metrics

Technical metrics:

- 126 documents registered.
- 90 percent plus searchable chunks.
- 700 verified questions seeded.
- 15+ critical amendments seeded.
- 45+ amendment questions generated.
- No duplicate dashboard endpoint.
- Smart mock saves complete lifecycle.
- Essay history persists.

Study metrics:

- All major topics above 70 percent accuracy.
- Top high-yield topics above 80 percent accuracy.
- Recent amendment mastery above 85 percent.
- Essay average above 75/100.
- Full mock average above 85.
- Wrong-answer repeat rate decreasing weekly.

Readiness metrics:

- Estimated score: 85-90.
- Confidence band shown honestly.
- No unmastered critical amendment.
- No critical topic below 65 percent in final week.

---

## 22. Risk Register

| Risk | Severity | Mitigation |
|---|---:|---|
| AI generates hallucinated regulatory facts | High | Require retrieval and citations before storage |
| Corpus is present but not ingested | High | Phase 1 is mandatory before advanced generation |
| Amendments become stale | High | Build amendment radar and manual import |
| Duplicate/incorrect routes break frontend | Medium | Consolidate API schemas |
| Gemini keys missing or rate-limited | Medium | Startup validation, local mock mode, key rotation |
| Topic taxonomy too shallow | Medium | Normalize topics and subtopics |
| Overbuilding delays studying | Medium | Build in phases and preserve daily usability |
| Score prediction overconfident | Medium | Use confidence bands and transparent formula |
| PDF extraction errors | Medium | Keep source references and manual correction path |
| Copyright/material handling | Medium | Use local personal study corpus; avoid redistribution features |

---

## 23. Immediate Next Implementation Order

The next work should not be random UI polish. Build in this order:

1. Fix backend route/schema issues.
2. Add Gemini key guard and local mock mode.
3. Add document registry and chunk tables.
4. Ingest all extracted text into searchable FTS.
5. Add source search endpoint and simple Knowledge Explorer.
6. Add normalized topic taxonomy.
7. Tag source chunks by topic.
8. Seed critical amendments with citations.
9. Upgrade question generation to retrieve source chunks first.
10. Save smart mock questions and support full attempt submission.
11. Add essay persistence and trend view.
12. Build amendment radar/manual import.
13. Build TCS iON-style exam mode.
14. Add analytics/prediction layer.

---

## 24. First 72-Hour Build Plan

### Day 1: Stabilize and ingest

- Consolidate `/api/dashboard`.
- Add no-key guard.
- Create migrations for document tables.
- Build ingestion script.
- Ingest the 126-document text corpus.
- Build source search.

Deliverable:

- App can search the full corpus.

### Day 2: Topic map and amendments

- Add topic table.
- Tag chunks by topic.
- Seed 15 critical amendments.
- Link amendments to citations.
- Generate first amendment questions.

Deliverable:

- App has an amendment tracker backed by real source citations.

### Day 3: Mock lifecycle

- Upgrade smart mock to use question bank and citations.
- Save mock questions.
- Add answer submission.
- Add review screen.
- Update analytics after submission.

Deliverable:

- User can take a source-grounded smart mock end to end.

---

## 25. Final Verdict

The project is in a strong but unfinished state.

What exists:

- A working FastAPI/SQLite prototype.
- Mock upload.
- Weak topic tracking.
- Penalty drill generation.
- Essay grading call.
- Amendment entry.
- Smart mock allocation logic.
- Large source corpus.
- Extensive planning and validation documents.

What is missing:

- Runtime ingestion of all 126 PDFs.
- Source-grounded question generation.
- Complete mock attempt lifecycle.
- Essay persistence and trend tracking.
- Seeded amendment database.
- Automated amendment radar.
- TCS-style exam interface.
- Mature analytics.

The correct next move is not to search endlessly for more PDFs. The correct next move is to convert the documents already collected into a working knowledge engine and wire that engine into mocks, drills, essays, and amendments.

This is the final north-star build:

Source-grounded knowledge engine first. Adaptive mocks second. Amendment mastery always. Essay improvement loop continuously. Analytics everywhere. Exam-mode polish after the core learning engine is trustworthy.


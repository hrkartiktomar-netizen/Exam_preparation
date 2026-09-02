"""
PYQ (Previous Year Question) Paper Parser

Parses memory-based and actual exam paper text to extract questions, options, and answers.
Uses regex patterns optimized for IFSCA exam paper format.

Per Context7 docs for Python: use re.VERBOSE for readable regex patterns and re.MULTILINE for line-based matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ParsedQuestion:
    """Represents a single parsed question from PYQ paper."""
    question_number: int
    question_text: str
    options: dict[str, str]  # {"A": "option text", "B": "...", etc.}
    correct_answer: str  # Single letter: A, B, C, D, or E
    direction_text: str | None = None  # Grouped direction/context if present


def parse_pyq_paper(raw_text: str) -> list[ParsedQuestion]:
    """
    Parse raw PYQ paper text into structured questions.

    Handles:
    - Question numbering (Q1, Q2, etc.)
    - Options (A., B., C., D., E.)
    - Answer keys (Answer: X)
    - Grouped instructions (Direction/Note text)
    - MULTI-SECTION papers with renumbered questions

    Per Context7 docs for Python: use re.MULTILINE | re.DOTALL for robust line matching.

    Args:
        raw_text: Full PYQ paper text as string

    Returns:
        List of ParsedQuestion objects in order with GLOBALLY unique question numbers

    Raises:
        ValueError: If text cannot be parsed (malformed format)
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Input text is empty")

    questions: list[ParsedQuestion] = []
    global_q_number = 1  # Track globally unique question numbers
    last_section = None  # Detect section changes

    # Simpler approach: split by "Q" then parse each block
    # This is more reliable than trying to match everything in one regex
    blocks = re.split(r'^Q(\d+)\.\s+', raw_text, flags=re.MULTILINE)

    # blocks will be: [prefix, q1_num, q1_content, q2_num, q2_content, ...]
    # Skip the prefix (index 0), then process pairs
    for i in range(1, len(blocks), 2):
        if i + 1 >= len(blocks):
            break

        q_num_str = blocks[i].strip()
        q_content = blocks[i + 1]

        try:
            section_q_num = int(q_num_str)
        except (ValueError, IndexError):
            continue  # Skip malformed question numbers

        # Detect if we've crossed into a new section
        # (This is rough heuristic: if max 2 questions back, we may be in new section)
        # Better heuristic: if question number is < the previous one, we're likely in a new section
        if len(questions) > 0 and section_q_num <= questions[-1].question_number:
            # Question number decreased or is same = new section detected
            # Reset tracking for new section
            pass

        # Parse options and answer from content
        try:
            parsed_q = _parse_question_content(global_q_number, q_content)
            if parsed_q:
                questions.append(parsed_q)
                global_q_number += 1  # Increment GLOBAL counter, not section counter
        except (ValueError, KeyError) as e:
            # Log but continue parsing other questions
            # In production, might want stricter handling
            continue

    if not questions:
        raise ValueError(f"No valid questions could be parsed from text (tried to parse {len(blocks)//2} blocks)")

    return questions


def _parse_question_content(q_num: int, content: str) -> ParsedQuestion | None:
    """
    Parse a single question's content block.

    Extracts:
    - Question text (before first option)
    - Options A-E (lines starting with A., B., C., D., E.)
    - Answer key (line with "Answer: X")

    Per Context7 docs: use try/finally for resource cleanup (not needed here but good practice).
    """
    lines = content.split('\n')

    question_text = ""
    options: dict[str, str] = {}
    answer: str | None = None
    in_options = False

    for line in lines:
        line = line.rstrip()
        if not line:
            continue

        # Check for option line: "A. Option text" or just "A." at line start
        option_match = re.match(r'^([A-E])\.\s+(.*)$', line)
        if option_match:
            opt_letter = option_match.group(1)
            opt_text = option_match.group(2).strip()
            options[opt_letter] = opt_text
            in_options = True
            continue

        # Check for answer line
        answer_match = re.match(r'^Answer:\s*([A-E])\s*$', line)
        if answer_match:
            answer = answer_match.group(1)
            continue

        # If we haven't hit options yet, accumulate as question text
        if not in_options:
            question_text += (" " + line.strip()) if question_text else line.strip()

    # Validate we got basics
    if not question_text or not answer:
        return None

    # We expect at least A and B, ideally A-E
    if len(options) < 2:
        return None

    # Ensure all present options are in standard order and cleaned
    cleaned_options = {k: v.strip() for k, v in options.items() if v.strip()}

    if not cleaned_options or answer not in cleaned_options:
        return None

    return ParsedQuestion(
        question_number=q_num,
        question_text=question_text.strip(),
        options=cleaned_options,
        correct_answer=answer,
        direction_text=None
    )


def pyq_to_dict(parsed_q: ParsedQuestion) -> dict[str, Any]:
    """Convert ParsedQuestion to JSON-serializable dict for API response."""
    return asdict(parsed_q)


# ============================================================================
# Consolidated question-bank parser (question_banks/*.md)
#
# Format: `**Q{n}.** stem`, options as `- (a) text` lines or inline
# `- (A) x (B) y ...`, answers as `> **Answer:** (x)` (or `(—)`), hints as
# `> **Hint:** ...`, paper headers `## IFSCA/SEBI Grade A {year} – ...`,
# section headers `### ...`, descriptive blocks with model answers.
# ============================================================================

BANK_Q_RE = re.compile(r"^\*\*Q(\d+)\.\*\*\s*(.*)$")
BANK_SUBQ_RE = re.compile(r"^\*\*(\d+)\.(\d+)\.\*\*\s*(.*)$")
BANK_OPT_LINE_RE = re.compile(r"^-\s*\(([A-Ea-e])\)\s*(.*)$")
BANK_OPT_INLINE_RE = re.compile(r"\(([A-E])\)")
BANK_ANSWER_RE = re.compile(r"^>\s*\*\*Answer:\*\*\s*\(?\s*([A-Ea-e]|—|-)\s*\)?\s*(.*)$")
BANK_LABEL_RE = re.compile(r"^>\s*\*\*(Model Answer(?:\s*\(([^)]*)\))?|Model Précis|Hint|Answer Hint|Answer):\*\*\s*(.*)$")
BANK_PAPER_RE = re.compile(r"^##\s+(IFSCA|SEBI)\s+Grade\s+A\s+(\d{4})\s*[–—-]\s*(.+)$", re.I)
BANK_MARKS_RE = re.compile(r"\((\d+)\s*Marks?\)", re.I)
BANK_WORDLIMIT_RE = re.compile(r"(?:in|of)\s+(?:about\s+)?(\d{2,3})\s*(?:[-–—]\s*(\d{2,3}))?\s*words", re.I)
BANK_STMT_REF_RE = re.compile(r"^(?:\d+(?:\s*,\s*\d+)*(?:\s+and\s+\d+)?\s*only\.?|\d+\s+[A-E],|\d+\s+[A-Z]\s*,)")

BANK_SECTION_SUBJECTS = {
    "quant": "SUBJ_QUANT",
    "quantitative aptitude": "SUBJ_QUANT",
    "reasoning": "SUBJ_REASONING",
    "logical reasoning": "SUBJ_REASONING",
    "english": "SUBJ_ENGLISH",
    "general english": "SUBJ_ENGLISH",
    "general awareness": "SUBJ_GA",
    "ga": "SUBJ_GA",
    "finance": "SUBJ_FINANCE",
    "management": "SUBJ_MANAGEMENT",
    "commerce and accounts": "SUBJ_COMMERCE_ACCOUNTS",
    "commerce & accounts": "SUBJ_COMMERCE_ACCOUNTS",
    "commerce and accountancy": "SUBJ_COMMERCE_ACCOUNTS",
    "costing": "SUBJ_COSTING",
    "economics": "SUBJ_ECONOMICS",
    "economics and social development": "SUBJ_ECONOMICS",
    "companies act": "SUBJ_COMPANIES_ACT",
    "essay writing": "SUBJ_ESSAY",
    "precis writing": "SUBJ_PRECIS",
    "précis writing": "SUBJ_PRECIS",
    "reading comprehension": "SUBJ_RC",
}

BANK_PHASE1_SUBJECTS = {"SUBJ_QUANT", "SUBJ_REASONING", "SUBJ_ENGLISH", "SUBJ_GA"}
BANK_DESCRIPTIVE_SUBJECTS = {"SUBJ_ESSAY", "SUBJ_PRECIS", "SUBJ_RC"}


def _bank_subject_for(section_name: str) -> str | None:
    cleaned = re.sub(r"^section\s*(?:[a-z0-9]+\s*[:\-]?\s*)?", "", section_name.strip(), flags=re.I)
    cleaned = re.sub(r"^\s*[-:]\s*", "", cleaned)
    cleaned = re.sub(r"\(q\d+.*$", "", cleaned, flags=re.I).strip(" :-")
    key = cleaned.lower()
    if key in BANK_SECTION_SUBJECTS:
        return BANK_SECTION_SUBJECTS[key]
    for name, subject in sorted(BANK_SECTION_SUBJECTS.items(), key=lambda item: len(item[0]), reverse=True):
        if name and name in key:
            return subject
    return None


def _bank_scope_from_header(header_tail: str) -> dict[str, Any]:
    scope: dict[str, Any] = {"phase": None, "paper": None}
    if re.search(r"Phase\s*1\s*&\s*2", header_tail, flags=re.I):
        return scope
    phase_match = re.search(r"Phase\s*(\d)", header_tail, flags=re.I)
    paper_match = re.search(r"Paper\s*(\d)", header_tail, flags=re.I)
    if phase_match:
        scope["phase"] = int(phase_match.group(1))
    if paper_match:
        scope["paper"] = int(paper_match.group(1))
    if "descriptive" in header_tail.lower():
        scope["paper"] = scope["paper"] or 1
    return scope


def _bank_infer_scope(exam: str, subject_id: str | None, scope: dict[str, Any]) -> tuple[int | None, int | None]:
    """Fill missing phase/paper for SEBI files from the subject.

    SEBI banks are inconsistent: combined 'Phase 1 & 2' files have neither,
    '2024 – Phase 1/2' files have phase but no paper. IFSCA headers are
    explicit and pass through unchanged.
    """
    phase, paper = scope.get("phase"), scope.get("paper")
    if exam != "SEBI" or (phase is not None and paper is not None):
        return phase, paper
    if subject_id in BANK_PHASE1_SUBJECTS:
        return (phase if phase is not None else 1), 1
    if subject_id in BANK_DESCRIPTIVE_SUBJECTS:
        return 2, 1
    if subject_id:
        return (phase if phase is not None else 2), 2
    return phase, paper


def _bank_stem_has_statements(stem: str) -> bool:
    return bool(re.search(r"^\s*\d+\.\s+\S", stem, flags=re.M)) or bool(re.search(r"[Ii]{1,3}\.\s+[A-Z]", stem))


def parse_question_bank_file(path: str, exam: str | None = None) -> dict[str, Any]:
    """Parse a consolidated question bank (IFSCA or SEBI) into structured data.

    Returns:
        {
          "exam": "IFSCA"|"SEBI",
          "objective": [ {exam, year, phase, paper, section, subject_id, qnum,
                          question_text, direction_text, options, answer, hint,
                          incomplete, incomplete_reason} ],
          "descriptive": [ {exam, year, phase, paper, section, subject_id, item_type,
                            qnum, prompt_text, topics, passage_text, model_answer,
                            model_answers, sub_questions, marks, word_limit_min,
                            word_limit_max, title_required, incomplete,
                            incomplete_reason} ],
          "papers": [ {exam, year, phase, paper, title, meta, objective_count,
                       descriptive_count} ],
        }
    """
    import os

    text = open(path, encoding="utf-8").read()
    lines = text.split("\n")
    if exam is None:
        exam = "SEBI" if "sebi" in os.path.basename(path).lower() else "IFSCA"
    exam = exam.upper()

    objective: list[dict[str, Any]] = []
    descriptive: list[dict[str, Any]] = []
    papers: list[dict[str, Any]] = []

    year: int | None = None
    scope: dict[str, Any] = {"phase": None, "paper": None}
    paper_title = ""
    paper_meta = ""
    section = ""
    subject_id: str | None = None
    directions: str | None = None

    current: dict[str, Any] | None = None  # objective question being built
    current_desc: dict[str, Any] | None = None  # descriptive item being built
    current_subq: dict[str, Any] | None = None  # RC sub-question being built
    block_label: str | None = None  # active `>` block: Hint/Model Answer/Model Précis
    block_topic: str | None = None  # model-answer topic qualifier
    block_lines: list[str] = []
    passage_mode = False
    descriptive_seen = False  # stream blocks after the first descriptive block are Phase 2 Paper 2

    paper_obj_count = 0
    paper_desc_count = 0

    def flush_block() -> None:
        nonlocal block_label, block_topic, block_lines
        content = "\n".join(block_lines).strip()
        if block_label and content:
            if block_label == "Hint" and current is not None:
                current["hint"] = content
            elif block_label == "Answer Hint" and current_desc is not None:
                current_desc["model_answer"] = content
            elif block_label == "Model Précis" and current_desc is not None:
                current_desc["model_answer"] = content
            elif block_label == "Model Answer" and current_desc is not None:
                if current_subq is not None:
                    current_subq["model_answer"] = content
                elif block_topic:
                    current_desc.setdefault("model_answers", {})[block_topic] = content
                else:
                    current_desc["model_answer"] = content
        block_label = None
        block_topic = None
        block_lines = []

    def flush_question() -> None:
        nonlocal current, current_subq
        if current is not None:
            current["question_text"] = current["question_text"].strip()
            stmt_ref = any(BANK_STMT_REF_RE.match(opt.strip()) for opt in current["options"].values())
            if stmt_ref and not _bank_stem_has_statements(current["question_text"]):
                current["incomplete"] = True
                current["incomplete_reason"] = "options_reference_missing_statements"
            if not current.get("answer"):
                current["incomplete"] = True
                current["incomplete_reason"] = current.get("incomplete_reason") or "missing_answer"
            objective.append(current)
            current = None
        current_subq = None

    def flush_descriptive() -> None:
        nonlocal current_desc, current_subq, passage_mode
        flush_question()
        if current_desc is not None:
            current_desc["prompt_text"] = current_desc["prompt_text"].strip()
            if current_desc.get("passage_text"):
                current_desc["passage_text"] = current_desc["passage_text"].strip()
            has_model = bool(current_desc.get("model_answer") or current_desc.get("model_answers"))
            if not has_model and current_desc["item_type"] == "RC":
                has_model = any(subq.get("model_answer") for subq in current_desc.get("sub_questions", []))
            has_body = bool(current_desc.get("passage_text") or current_desc.get("topics"))
            if not has_model or not has_body:
                current_desc["incomplete"] = True
                current_desc["incomplete_reason"] = "prompt_only"
            descriptive.append(current_desc)
            current_desc = None
        current_subq = None
        passage_mode = False

    def flush_paper() -> None:
        nonlocal paper_obj_count, paper_desc_count
        if paper_title:
            papers.append({
                "exam": exam,
                "year": year,
                "phase": scope.get("phase"),
                "paper": scope.get("paper"),
                "title": paper_title,
                "meta": paper_meta,
                "objective_count": paper_obj_count,
                "descriptive_count": paper_desc_count,
            })
        paper_obj_count = 0
        paper_desc_count = 0

    for raw_line in lines:
        line = raw_line.rstrip()

        paper_header = BANK_PAPER_RE.match(line)
        if paper_header:
            flush_block()
            flush_descriptive()
            flush_paper()
            year = int(paper_header.group(2))
            scope = _bank_scope_from_header(paper_header.group(3))
            paper_title = line.lstrip("# ").strip()
            paper_meta = ""
            section = ""
            subject_id = None
            directions = None
            descriptive_seen = False
            continue

        if line.startswith("### "):
            flush_block()
            flush_descriptive()
            flush_question()
            section = line[4:].strip().strip("*").strip()
            subject_id = _bank_subject_for(section)
            directions = None
            if subject_id in BANK_DESCRIPTIVE_SUBJECTS:
                descriptive_seen = True
                inferred_phase, inferred_paper = _bank_infer_scope(exam, subject_id, scope)
                item_type = {"SUBJ_ESSAY": "ESSAY", "SUBJ_PRECIS": "PRECIS", "SUBJ_RC": "RC"}[subject_id]
                marks_match = BANK_MARKS_RE.search(section)
                current_desc = {
                    "exam": exam,
                    "year": year,
                    "phase": scope.get("phase") if scope.get("phase") else inferred_phase,
                    "paper": scope.get("paper") if scope.get("paper") else inferred_paper,
                    "section": section,
                    "subject_id": subject_id,
                    "item_type": item_type,
                    "qnum": None,
                    "prompt_text": "",
                    "topics": [],
                    "passage_text": "",
                    "model_answer": "",
                    "sub_questions": [],
                    "marks": int(marks_match.group(1)) if marks_match else None,
                    "word_limit_min": None,
                    "word_limit_max": None,
                    "title_required": item_type == "PRECIS",
                    "incomplete": False,
                    "incomplete_reason": None,
                }
                paper_desc_count += 1
            continue

        if line.startswith("**Total Questions:**"):
            paper_meta = line.strip("*").strip()
            continue

        directions_match = re.match(r"^\*\*Directions(?:\s*\(([^)]*)\))?:\*\*\s*(.*)$", line)
        if directions_match:
            flush_block()
            directions = (directions_match.group(2) or "").strip()
            continue

        q_match = BANK_Q_RE.match(line)
        if q_match:
            flush_block()
            flush_question()
            qnum = int(q_match.group(1))
            stem_rest = (q_match.group(2) or "").strip()
            if current_desc is not None:
                current_desc["qnum"] = qnum
                current_desc["prompt_text"] = stem_rest
                word_limit = BANK_WORDLIMIT_RE.search(stem_rest)
                if word_limit:
                    current_desc["word_limit_min"] = int(word_limit.group(1))
                    if word_limit.group(2):
                        current_desc["word_limit_max"] = int(word_limit.group(2))
                marks_match = BANK_MARKS_RE.search(stem_rest)
                if marks_match and not current_desc.get("marks"):
                    current_desc["marks"] = int(marks_match.group(1))
                continue
            if exam == "SEBI" and scope.get("phase") is None and subject_id and subject_id not in BANK_PHASE1_SUBJECTS and subject_id not in BANK_DESCRIPTIVE_SUBJECTS:
                inferred_phase, inferred_paper = (2, 2) if descriptive_seen else (1, 2)
            else:
                inferred_phase, inferred_paper = _bank_infer_scope(exam, subject_id, scope)
            current = {
                "exam": exam,
                "year": year,
                "phase": scope.get("phase") if scope.get("phase") else inferred_phase,
                "paper": scope.get("paper") if scope.get("paper") else inferred_paper,
                "section": section,
                "subject_id": subject_id,
                "qnum": qnum,
                "question_text": stem_rest,
                "direction_text": directions,
                "options": {},
                "answer": None,
                "hint": "",
                "incomplete": False,
                "incomplete_reason": None,
            }
            paper_obj_count += 1
            continue

        subq_match = BANK_SUBQ_RE.match(line)
        if subq_match and current_desc is not None and current_desc["item_type"] == "RC":
            flush_block()
            current_subq = {
                "qnum": f"{subq_match.group(1)}.{subq_match.group(2)}",
                "question": (subq_match.group(3) or "").strip(),
                "model_answer": "",
            }
            current_desc["sub_questions"].append(current_subq)
            passage_mode = False
            continue

        opt_match = BANK_OPT_LINE_RE.match(line)
        if opt_match and current is not None:
            flush_block()
            letter = opt_match.group(1).upper()
            rest = opt_match.group(2).strip()
            inline = BANK_OPT_INLINE_RE.findall(rest)
            if len(inline) >= 2:
                parts = re.split(r"\(([A-E])\)\s*", rest)
                # parts: ['', 'A', 'text ', 'B', 'text ', ...]
                for index in range(1, len(parts) - 1, 2):
                    current["options"][parts[index]] = parts[index + 1].strip()
            else:
                current["options"][letter] = rest
            continue

        label_match = BANK_LABEL_RE.match(line)
        if label_match:
            flush_block()
            label = label_match.group(1)
            block_topic = label_match.group(2)
            first = (label_match.group(3) or "").strip()
            if label == "Answer" and current is not None and current_desc is None:
                ans_match = BANK_ANSWER_RE.match(line)
                letter = ans_match.group(1).upper() if ans_match else ""
                current["answer"] = letter if letter in "ABCDE" else None
                continue
            block_label = "Model Answer" if label.startswith("Model Answer") else label
            block_lines = [first] if first else []
            continue

        if line.startswith(">"):
            content = line.lstrip(">").strip()
            if block_label is not None:
                block_lines.append(content)
                continue
            if current_desc is not None and passage_mode:
                current_desc["passage_text"] += content + "\n"
            continue

        if line.strip() == "---":
            flush_block()
            continue

        if line.startswith("**Passage:**"):
            if current_desc is not None:
                flush_block()
                passage_mode = True
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if current is not None:
            if current.get("answer") and block_label is None:
                continue  # prose after the answer line belongs to nothing
            current["question_text"] += "\n" + stripped
            continue
        if current_desc is not None:
            topic_match = re.match(r"^\d+\.\s+(.*)$", stripped)
            if current_desc["item_type"] == "ESSAY" and topic_match and not current_desc.get("model_answer") and not current_desc.get("model_answers"):
                current_desc["topics"].append(topic_match.group(1).strip())
                continue
            if passage_mode:
                current_desc["passage_text"] += stripped + "\n"
                continue
            if not current_desc["prompt_text"]:
                current_desc["prompt_text"] = stripped
            elif current_desc["item_type"] == "RC" and current_subq is None:
                current_desc["passage_text"] += stripped + "\n"
            continue

    flush_block()
    flush_descriptive()
    flush_paper()

    return {"exam": exam, "objective": objective, "descriptive": descriptive, "papers": papers}

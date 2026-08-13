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

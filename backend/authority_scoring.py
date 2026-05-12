"""Authority scoring for source documents and chunks."""

from typing import Any


def source_authority_score(doc_type: str, category: str, exam_signal: float = 0.0) -> int:
    """
    Calculate authority score for a source document using weighted formula.

    Formula: 0.52×official + 0.30×exam_signal + 0.18×confidence

    Args:
        doc_type: Type of document (e.g., "ifsca_regulation", "exam_paper", "coaching")
        category: Document category (e.g., "regulations", "annual_report", "bulletin")
        exam_signal: Optional exam signal score (0-100), defaults to 0

    Returns:
        Authority score 0-100 where 100 is highest authority
    """
    # Official source weighting
    official_score_map = {
        "ifsca_regulation": 95,  # Official IFSCA regulations
        "ifsca_bulletin": 90,    # Official IFSCA bulletins
        "rbi_notification": 85,  # Official RBI notifications
        "icsi_material": 80,     # Official ICSI study materials
        "pyx_paper": 75,         # Previous year exam papers
        "coaching_notes": 40,    # Coaching institute notes
        "extracted_pdf": 50,     # Generic extracted PDFs
        "default": 30,           # Unknown type
    }

    official_score = official_score_map.get(doc_type, official_score_map["default"])

    # Confidence boost for specific categories
    confidence_score_map = {
        "regulations": 90,
        "annual_report": 75,
        "bulletin": 85,
        "exam_paper": 95,
        "amendment": 88,
        "default": 50,
    }

    confidence_score = confidence_score_map.get(category, confidence_score_map["default"])

    # Ensure exam_signal is in valid range
    exam_signal = max(0, min(100, exam_signal))

    # Apply weighted formula: 0.52×official + 0.30×exam_signal + 0.18×confidence
    authority_score = (
        0.52 * official_score +
        0.30 * exam_signal +
        0.18 * confidence_score
    )

    return int(round(authority_score))


def rank_sources_for_topic(
    sources: list[dict[str, Any]], by_field: str = "authority_score"
) -> list[dict[str, Any]]:
    """
    Sort list of sources by authority score (descending) or other field.

    Args:
        sources: List of source dicts with authority_score field
        by_field: Field to sort by (default: authority_score)

    Returns:
        Sorted list of sources (highest authority first)
    """
    if not sources:
        return []

    return sorted(sources, key=lambda x: x.get(by_field, 0), reverse=True)


def boost_authority_for_match(
    base_score: int, keyword_matches: int, frequency: float = 1.0
) -> int:
    """
    Boost authority score based on keyword frequency in source.

    Args:
        base_score: Initial authority score (0-100)
        keyword_matches: Number of keyword matches found
        frequency: Frequency ratio (0-1.0)

    Returns:
        Boosted authority score, capped at 100
    """
    if base_score < 0 or base_score > 100:
        return base_score

    # Boost logic: +5 per keyword match, up to +20 total
    boost = min(20, keyword_matches * 5)

    # Apply frequency multiplier
    boost = int(boost * frequency)

    final_score = base_score + boost
    return min(100, final_score)

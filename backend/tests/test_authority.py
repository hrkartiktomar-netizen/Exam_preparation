"""Test suite for Phase 0: Authority Scoring Functionality"""

import sys
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from authority_scoring import (
    source_authority_score,
    rank_sources_for_topic,
    boost_authority_for_match,
)


class TestAuthority:
    """Authority scoring formula and ranking tests."""

    def test_official_source_scores_highest(self):
        """TEST 1: Official IFSCA documents score highest."""
        print("\n[TEST 1] test_official_source_scores_highest")

        # Score official IFSCA regulation
        official_score = source_authority_score("ifsca_regulation", "regulations")
        print(f"  IFSCA Regulation score: {official_score}")

        # Score coaching notes
        coaching_score = source_authority_score("coaching_notes", "default")
        print(f"  Coaching Notes score: {coaching_score}")

        # Official should score significantly higher
        assert official_score > coaching_score, \
            f"Official ({official_score}) should > Coaching ({coaching_score})"

        assert official_score >= 60, \
            f"Official IFSCA should score >=60, got {official_score}"

        print(f"  [OK] PASS: Official scores higher ({official_score} > {coaching_score})")

    def test_exam_signal_bonus(self):
        """TEST 2: Exam signal provides scoring boost."""
        print("\n[TEST 2] test_exam_signal_bonus")

        # Score without exam signal
        base_score = source_authority_score(
            "coaching_notes", "default", exam_signal=0
        )
        print(f"  Base score (no signal): {base_score}")

        # Score with strong exam signal
        boosted_score = source_authority_score(
            "coaching_notes", "default", exam_signal=100
        )
        print(f"  Boosted score (exam=100): {boosted_score}")

        # Exam signal should increase score
        assert boosted_score > base_score, \
            f"Boosted ({boosted_score}) should > Base ({base_score})"

        boost_value = boosted_score - base_score
        assert boost_value > 10, \
            f"Exam signal should boost by >10 points, got +{boost_value}"

        print(f"  [OK] PASS: Exam signal boosts score by +{boost_value}")

    def test_rank_sources_sorted(self):
        """TEST 3: Source ranking sorts by authority descending."""
        print("\n[TEST 3] test_rank_sources_sorted")

        # Create test sources
        sources = [
            {"name": "Coaching", "authority_score": 40},
            {"name": "IFSCA Regulation", "authority_score": 90},
            {"name": "Bulletin", "authority_score": 75},
            {"name": "Exam Paper", "authority_score": 95},
        ]

        ranked = rank_sources_for_topic(sources)

        print(f"  Input order: {[s['name'] for s in sources]}")
        print(f"  Ranked order: {[s['name'] for s in ranked]}")
        print(f"  Scores: {[s['authority_score'] for s in ranked]}")

        # Verify sorted descending
        scores = [s["authority_score"] for s in ranked]
        assert scores == sorted(scores, reverse=True), \
            f"Scores not sorted descending: {scores}"

        # First should be Exam Paper (95)
        assert ranked[0]["name"] == "Exam Paper", \
            f"First should be Exam Paper, got {ranked[0]['name']}"

        print(f"  [OK] PASS: Sources ranked correctly by authority")

    def test_authority_score_formula_correct(self):
        """Validate the exact formula: 0.52×official + 0.30×exam + 0.18×confidence."""
        print("\n[TEST-VERIFY] Formula validation")

        # Create specific score to verify formula
        # Using default "extracted_pdf" type (official=50) + exam_signal=50 + category default (conf=50)
        score = source_authority_score("extracted_pdf", "default", exam_signal=50)

        # Expected: 0.52*50 + 0.30*50 + 0.18*50 = 26 + 15 + 9 = 50
        expected = int(0.52 * 50 + 0.30 * 50 + 0.18 * 50)

        print(f"  Formula: 0.52×50 + 0.30×50 + 0.18×50 = {expected}")
        print(f"  Actual result: {score}")

        assert score == expected, \
            f"Formula mismatch: expected {expected}, got {score}"

        print(f"  [OK] PASS: Formula verified")


if __name__ == "__main__":
    """Run authority scoring tests directly."""
    test_suite = TestAuthority()

    try:
        print("=" * 60)
        print("PHASE 0 - AUTHORITY SCORING TESTS")
        print("=" * 60)

        test_suite.test_official_source_scores_highest()
        test_suite.test_exam_signal_bonus()
        test_suite.test_rank_sources_sorted()
        test_suite.test_authority_score_formula_correct()

        print("\n" + "=" * 60)
        print("ALL AUTHORITY TESTS PASSED [OK]")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[FAIL] TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

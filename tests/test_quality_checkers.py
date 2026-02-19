"""Tests for the quality verification system."""

import pytest
from src.verification.quality_checkers import (
    FactChecker, FlowChecker, FormatChecker, CulturalChecker,
    LLMFactChecker, run_all_checkers, aggregate_quality_score, should_revise
)


class TestFactChecker:
    def test_fully_cited_segments(self, sample_segments, sample_state):
        """Segments with citations should score well."""
        # Add fact IDs to state
        sample_state["fact_entity_ids"] = ["fact_001", "fact_002", "fact_003"]

        checker = FactChecker()
        result = checker.check(sample_segments, sample_state)

        assert result.checker_name == "fact_checker"
        assert result.score > 0.0

    def test_unknown_citations_flagged(self, sample_segments, sample_state):
        """Citations not in the KG should be flagged."""
        sample_state["fact_entity_ids"] = []  # No known facts

        checker = FactChecker()
        result = checker.check(sample_segments, sample_state)

        assert any("not in graph" in issue for issue in result.issues)

    def test_empty_segments(self, sample_state):
        checker = FactChecker()
        result = checker.check([], sample_state)
        assert result.passed


class TestFlowChecker:
    def test_balanced_conversation(self, sample_segments, sample_state):
        checker = FlowChecker()
        result = checker.check(sample_segments, sample_state)

        assert result.checker_name == "flow_checker"
        assert result.score > 0.0

    def test_short_script_flagged(self, sample_state):
        from src.models.state import DialogueSegment
        short = [
            DialogueSegment(speaker="Host", text="Hi", timestamp=0, fact_ids=[]),
            DialogueSegment(speaker="Expert", text="Hello", timestamp=1, fact_ids=[]),
        ]

        checker = FlowChecker()
        result = checker.check(short, sample_state)
        assert not result.passed
        assert result.score < 0.5


class TestFormatChecker:
    def test_duration_check(self, sample_segments, sample_state):
        sample_state["target_duration_minutes"] = 5
        checker = FormatChecker()
        result = checker.check(sample_segments, sample_state)

        assert result.checker_name == "format_checker"
        # Script is very short for 5 min target
        assert any("short" in issue.lower() or "Missing" in issue for issue in result.issues)

    def test_intro_outro_detection(self, sample_segments, sample_state):
        checker = FormatChecker()
        result = checker.check(sample_segments, sample_state)
        # First segment has "Welcome", last has "Tune in"
        assert not any("Missing introduction" in issue for issue in result.issues)


class TestCulturalChecker:
    def test_english_passes(self, sample_segments, sample_state):
        sample_state["target_language"] = "english"
        checker = CulturalChecker()
        result = checker.check(sample_segments, sample_state)
        assert result.passed

    def test_sensitive_language_flagged(self, sample_state):
        from src.models.state import DialogueSegment
        segments = [
            DialogueSegment(speaker="Host", text="That was such a stupid idea", timestamp=0, fact_ids=[])
        ]
        checker = CulturalChecker()
        result = checker.check(segments, sample_state)
        assert any("insensitive" in issue.lower() for issue in result.issues)


class TestRunAllCheckers:
    def test_runs_all_checkers(self, sample_segments, sample_state):
        sample_state["fact_entity_ids"] = ["fact_001", "fact_002", "fact_003"]
        results = run_all_checkers(sample_segments, sample_state)

        # Should have 5 checkers including LLM fact checker
        assert len(results) >= 4
        checker_names = {r.checker_name for r in results}
        assert "fact_checker" in checker_names
        assert "flow_checker" in checker_names
        assert "format_checker" in checker_names
        assert "cultural_checker" in checker_names

    def test_aggregate_score(self, sample_segments, sample_state):
        sample_state["fact_entity_ids"] = ["fact_001", "fact_002", "fact_003"]
        results = run_all_checkers(sample_segments, sample_state)
        score = aggregate_quality_score(results)
        assert 0.0 <= score <= 1.0

    def test_should_revise_low_quality(self):
        from src.models.state import VerificationResult
        bad_results = [
            VerificationResult(checker_name="fact_checker", passed=False, score=0.2, issues=["bad"], suggestions=[]),
            VerificationResult(checker_name="flow_checker", passed=True, score=0.8, issues=[], suggestions=[]),
        ]
        assert should_revise(bad_results)

    def test_should_not_revise_high_quality(self):
        from src.models.state import VerificationResult
        good_results = [
            VerificationResult(checker_name="fact_checker", passed=True, score=0.9, issues=[], suggestions=[]),
            VerificationResult(checker_name="flow_checker", passed=True, score=0.9, issues=[], suggestions=[]),
            VerificationResult(checker_name="format_checker", passed=True, score=0.9, issues=[], suggestions=[]),
            VerificationResult(checker_name="cultural_checker", passed=True, score=0.9, issues=[], suggestions=[]),
        ]
        assert not should_revise(good_results)

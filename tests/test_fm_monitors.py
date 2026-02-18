"""Tests for the FM (Foundation Model) monitors."""

import pytest
from src.models.state import LightweightHandoff
from src.verification.fm_monitors import (
    run_all_monitors, calculate_fm_reward
)


@pytest.fixture
def good_handoff():
    return LightweightHandoff(
        summary="Extracted 3 topics, 8 facts from 2 inputs",
        confidence=0.9,
        completeness=0.95,
        relevant_entities=["topic_001", "fact_001", "fact_002"],
        known_gaps=[],
        flags=["needs_fact_check"],
        requires_from_next=["generate_script"],
        full_context_ref="state.extracted_content",
        source_agent="gatherer"
    )


@pytest.fixture
def previous_handoff():
    return LightweightHandoff(
        summary="Routed 2 inputs via research",
        confidence=0.85,
        completeness=1.0,
        relevant_entities=["topic_001"],
        known_gaps=[],
        flags=[],
        requires_from_next=["extract_content"],
        full_context_ref="state.input_contents",
        source_agent="router"
    )


@pytest.fixture
def minimal_state(sample_state):
    return sample_state


class TestFMMonitors:
    def test_run_all_monitors(self, good_handoff, previous_handoff, minimal_state):
        """All monitors should run without error."""
        results = run_all_monitors(good_handoff, [previous_handoff], minimal_state)

        assert len(results) > 0
        for r in results:
            assert hasattr(r, 'monitor_name')
            assert hasattr(r, 'reward_signal')
            assert hasattr(r, 'triggered')

    def test_calculate_fm_reward(self, good_handoff, previous_handoff, minimal_state):
        """FM reward should be a float in [-1, 1] range."""
        results = run_all_monitors(good_handoff, [previous_handoff], minimal_state)
        reward = calculate_fm_reward(results)

        assert isinstance(reward, float)
        assert -1.0 <= reward <= 1.0

    def test_high_confidence_rewarded(self, good_handoff, previous_handoff, minimal_state):
        """High confidence handoffs should get positive rewards."""
        good_handoff.confidence = 0.95
        good_handoff.completeness = 1.0
        results = run_all_monitors(good_handoff, [previous_handoff], minimal_state)
        reward = calculate_fm_reward(results)

        # Should be non-negative for good handoff
        assert reward >= 0

    def test_empty_previous_handoffs(self, good_handoff, minimal_state):
        """Should handle empty previous handoffs."""
        results = run_all_monitors(good_handoff, [], minimal_state)
        assert len(results) > 0

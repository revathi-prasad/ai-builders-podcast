"""
Shared test fixtures for the AI Podcast Generator test suite.
"""

import os
import sys
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any, List

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory that's cleaned up after test."""
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def sample_state() -> Dict[str, Any]:
    """Create a minimal PodcastState-like dict for testing."""
    from src.models.state import (
        PodcastState, ContentItem, ContentType,
        ProcessingStatus, create_initial_state
    )

    return create_initial_state(
        user_request="Explain machine learning basics",
        input_contents=[
            ContentItem(content_type=ContentType.TOPIC, source="Machine Learning")
        ],
        target_language="english",
        target_duration_minutes=5,
        episode_format="conversation",
        audience_level="beginner"
    )


@pytest.fixture
def sample_segments():
    """Create sample DialogueSegments for testing."""
    from src.models.state import DialogueSegment

    return [
        DialogueSegment(
            speaker="Host",
            text="Welcome to our podcast! Today we're diving into machine learning.",
            timestamp=0,
            fact_ids=["fact_001"]
        ),
        DialogueSegment(
            speaker="Expert",
            text="Great topic! Machine learning is a subset of AI that learns from data.",
            timestamp=1,
            fact_ids=["fact_002"]
        ),
        DialogueSegment(
            speaker="Host",
            text="That's fascinating. Can you explain how it actually works?",
            timestamp=2,
            fact_ids=[]
        ),
        DialogueSegment(
            speaker="Expert",
            text="Absolutely. Think of it like teaching by example. You show the model thousands of examples, and it finds patterns.",
            timestamp=3,
            fact_ids=["fact_003"]
        ),
        DialogueSegment(
            speaker="Host",
            text="Thank you for joining us! Tune in next time for more insights.",
            timestamp=4,
            fact_ids=[]
        ),
    ]


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    client = AsyncMock()
    response = MagicMock()
    response.content = '{"result": "test output"}'
    client.generate.return_value = response
    return client


@pytest.fixture
def mock_kg_manager(tmp_dir):
    """Create a KG manager that uses a temp directory."""
    from src.graph.manager import KnowledgeGraphManager
    kg = KnowledgeGraphManager(db_path=os.path.join(tmp_dir, "test_kg"))
    try:
        kg.initialize()
        yield kg
    except ImportError:
        # kuzu not installed — return a mock
        mock = MagicMock()
        mock.add_topic.return_value = "topic_test_001"
        mock.add_fact.return_value = "fact_test_001"
        mock.add_source.return_value = "src_test_001"
        mock.get_facts_about_topic.return_value = []
        yield mock
    finally:
        try:
            kg.close()
        except Exception:
            pass

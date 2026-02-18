"""
Text Processor for raw text and topic inputs

This module handles:
- Raw text input from users
- Topic strings that need research
- Text cleaning and normalization
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import hashlib
import re


@dataclass
class ProcessedText:
    """Processed text content"""
    text: str
    word_count: int
    sentence_count: int
    topics: List[str] = field(default_factory=list)
    entities: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_hash: str = ""
    processing_timestamp: datetime = field(default_factory=datetime.now)


class TextProcessor:
    """
    Process raw text input.

    Usage:
        processor = TextProcessor()
        result = processor.process("Your text here...")
        print(result.word_count)
        print(result.topics)
    """

    def __init__(
        self,
        extract_topics: bool = True,
        clean_text: bool = True,
        min_word_count: int = 10
    ):
        """
        Initialize the text processor.

        Args:
            extract_topics: Whether to extract topic keywords
            clean_text: Whether to normalize whitespace/formatting
            min_word_count: Minimum words for valid input
        """
        self.extract_topics = extract_topics
        self.clean_text = clean_text
        self.min_word_count = min_word_count

    def process(self, text: str) -> ProcessedText:
        """
        Process raw text input.

        Args:
            text: The text to process

        Returns:
            ProcessedText with analysis
        """
        if not text or not text.strip():
            raise ValueError("Empty text input")

        # Clean text if requested
        if self.clean_text:
            text = self._clean_text(text)

        # Calculate hash
        text_hash = hashlib.md5(text.encode()).hexdigest()

        # Basic stats
        word_count = len(text.split())
        sentence_count = len(re.split(r'[.!?]+', text))

        if word_count < self.min_word_count:
            raise ValueError(
                f"Text too short: {word_count} words "
                f"(minimum: {self.min_word_count})"
            )

        # Extract topics if requested
        topics = []
        if self.extract_topics:
            topics = self._extract_keywords(text)

        return ProcessedText(
            text=text,
            word_count=word_count,
            sentence_count=sentence_count,
            topics=topics,
            entities=[],  # Could use NER here
            metadata={
                "avg_word_length": sum(len(w) for w in text.split()) / word_count,
                "paragraphs": text.count('\n\n') + 1
            },
            source_hash=text_hash
        )

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        # Fix common encoding issues
        text = text.replace('\u2019', "'")  # Smart quotes
        text = text.replace('\u201c', '"')
        text = text.replace('\u201d', '"')
        text = text.replace('\u2014', ' - ')  # Em dash

        # Remove excessive punctuation
        text = re.sub(r'([.!?])\1+', r'\1', text)

        return text.strip()

    def _extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """
        Extract keyword topics from text.

        This is a simple implementation using word frequency.
        For production, consider using:
        - KeyBERT
        - YAKE
        - RAKE
        """
        # Common stopwords
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
            'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
            'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
            'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
            'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there'
        }

        # Tokenize and count
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        word_counts = {}

        for word in words:
            if word not in stopwords:
                word_counts[word] = word_counts.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

        return [word for word, count in sorted_words[:top_n]]

    def process_topic(self, topic: str) -> Dict[str, Any]:
        """
        Process a topic string (not full text).

        This is for when users just provide a topic like
        "AI in Healthcare" without any content.

        Args:
            topic: The topic string

        Returns:
            Dict with topic analysis
        """
        topic = topic.strip()

        if not topic:
            raise ValueError("Empty topic")

        # Detect if it's a question
        is_question = topic.endswith('?') or any(
            topic.lower().startswith(w) for w in ['what', 'why', 'how', 'when', 'where', 'who', 'which']
        )

        # Extract potential sub-topics
        subtopics = re.split(r'[,;]|\band\b|\bor\b', topic)
        subtopics = [s.strip() for s in subtopics if s.strip()]

        return {
            "topic": topic,
            "is_question": is_question,
            "subtopics": subtopics,
            "word_count": len(topic.split()),
            "requires_research": True  # Topics need web research
        }

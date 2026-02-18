"""
Router Agent for Input Classification and Workflow Orchestration

This agent analyzes user input and determines:
1. Content type (document, audio, URL, topic, mixed)
2. Processing requirements
3. Workflow path through the multi-agent system

Uses Claude for intelligent classification with fallback heuristics.
"""

import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Types of content that can be processed"""
    DOCUMENT = "document"      # PDF, DOCX, TXT
    AUDIO = "audio"           # MP3, WAV, M4A (transcription needed)
    VIDEO = "video"           # MP4, YouTube (extract audio + transcribe)
    URL = "url"               # Web article to scrape
    TOPIC = "topic"           # Just a topic/prompt to research
    TEXT = "text"             # Raw text provided directly
    MIXED = "mixed"           # Multiple content types


class ProcessingPath(Enum):
    """Workflow paths based on input analysis"""
    TRANSCRIBE_THEN_GENERATE = "transcribe_then_generate"  # Audio/video → text → script
    EXTRACT_THEN_GENERATE = "extract_then_generate"        # PDF/doc → text → script
    SCRAPE_THEN_GENERATE = "scrape_then_generate"          # URL → text → script
    RESEARCH_THEN_GENERATE = "research_then_generate"      # Topic → research → script
    DIRECT_GENERATE = "direct_generate"                     # Text → script directly
    MULTI_SOURCE = "multi_source"                          # Multiple paths combined


@dataclass
class ContentInput:
    """A single piece of input content"""
    source: str                    # File path, URL, or text content
    content_type: ContentType
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """Result of routing analysis"""
    inputs: List[ContentInput]
    primary_path: ProcessingPath
    requires_transcription: bool
    requires_extraction: bool
    requires_scraping: bool
    requires_research: bool
    estimated_complexity: Literal["simple", "moderate", "complex"]
    suggested_duration_minutes: int
    language_detected: str
    topics_identified: List[str]
    warnings: List[str] = field(default_factory=list)


# File extension mappings
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".rtf", ".odt"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# URL patterns
YOUTUBE_PATTERN = re.compile(
    r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)[\w-]+'
)
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')


class RouterAgent:
    """
    Intelligent router that analyzes input and determines processing path

    Can use Claude for nuanced classification or fall back to heuristics.
    """

    def __init__(self, use_llm: bool = True, anthropic_client: Any = None):
        self.use_llm = use_llm and anthropic_client is not None
        self.client = anthropic_client

    def route(
        self,
        user_request: str,
        contents: List[Dict[str, str]],
        target_language: str = "english",
        target_duration: int = 10
    ) -> RoutingDecision:
        """
        Analyze inputs and determine routing

        Args:
            user_request: User's description of what they want
            contents: List of {"type": str, "source": str} dicts
            target_language: Desired output language
            target_duration: Target podcast duration in minutes

        Returns:
            RoutingDecision with complete analysis
        """
        # Classify each input
        classified_inputs = []
        for content in contents:
            input_type = self._classify_content(content["type"], content["source"])
            classified_inputs.append(ContentInput(
                source=content["source"],
                content_type=input_type,
                metadata={"original_type": content["type"]}
            ))

        # If no content provided, treat as topic-based
        if not classified_inputs:
            classified_inputs.append(ContentInput(
                source=user_request,
                content_type=ContentType.TOPIC,
                metadata={"from_request": True}
            ))

        # Determine processing requirements
        requires_transcription = any(
            c.content_type in (ContentType.AUDIO, ContentType.VIDEO)
            for c in classified_inputs
        )
        requires_extraction = any(
            c.content_type == ContentType.DOCUMENT
            for c in classified_inputs
        )
        requires_scraping = any(
            c.content_type == ContentType.URL
            for c in classified_inputs
        )
        requires_research = any(
            c.content_type == ContentType.TOPIC
            for c in classified_inputs
        )

        # Determine primary path
        primary_path = self._determine_path(
            classified_inputs,
            requires_transcription,
            requires_extraction,
            requires_scraping,
            requires_research
        )

        # Estimate complexity
        complexity = self._estimate_complexity(
            classified_inputs,
            target_duration,
            requires_transcription
        )

        # Extract topics from request
        topics = self._extract_topics(user_request, classified_inputs)

        # Detect language
        language = self._detect_language(user_request, target_language)

        # Generate warnings
        warnings = self._generate_warnings(classified_inputs, target_duration)

        return RoutingDecision(
            inputs=classified_inputs,
            primary_path=primary_path,
            requires_transcription=requires_transcription,
            requires_extraction=requires_extraction,
            requires_scraping=requires_scraping,
            requires_research=requires_research,
            estimated_complexity=complexity,
            suggested_duration_minutes=target_duration,
            language_detected=language,
            topics_identified=topics,
            warnings=warnings
        )

    def _classify_content(self, declared_type: str, source: str) -> ContentType:
        """Classify a single piece of content"""
        # Trust declared type if specific
        type_map = {
            "document": ContentType.DOCUMENT,
            "audio": ContentType.AUDIO,
            "video": ContentType.VIDEO,
            "url": ContentType.URL,
            "topic": ContentType.TOPIC,
            "text": ContentType.TEXT,
        }

        if declared_type.lower() in type_map:
            return type_map[declared_type.lower()]

        # Infer from source
        source_lower = source.lower()

        # Check for YouTube
        if YOUTUBE_PATTERN.match(source):
            return ContentType.VIDEO

        # Check for other URLs
        if URL_PATTERN.match(source):
            return ContentType.URL

        # Check file extension
        if os.path.exists(source):
            ext = Path(source).suffix.lower()
            if ext in DOCUMENT_EXTENSIONS:
                return ContentType.DOCUMENT
            if ext in AUDIO_EXTENSIONS:
                return ContentType.AUDIO
            if ext in VIDEO_EXTENSIONS:
                return ContentType.VIDEO

        # Check if it looks like a file path
        path = Path(source)
        ext = path.suffix.lower()
        if ext in DOCUMENT_EXTENSIONS:
            return ContentType.DOCUMENT
        if ext in AUDIO_EXTENSIONS:
            return ContentType.AUDIO
        if ext in VIDEO_EXTENSIONS:
            return ContentType.VIDEO

        # Default: if short, treat as topic; if long, treat as text
        if len(source) < 100:
            return ContentType.TOPIC
        return ContentType.TEXT

    def _determine_path(
        self,
        inputs: List[ContentInput],
        transcription: bool,
        extraction: bool,
        scraping: bool,
        research: bool
    ) -> ProcessingPath:
        """Determine the primary processing path"""
        active_paths = sum([transcription, extraction, scraping, research])

        if active_paths == 0:
            return ProcessingPath.DIRECT_GENERATE

        if active_paths > 1:
            return ProcessingPath.MULTI_SOURCE

        if transcription:
            return ProcessingPath.TRANSCRIBE_THEN_GENERATE
        if extraction:
            return ProcessingPath.EXTRACT_THEN_GENERATE
        if scraping:
            return ProcessingPath.SCRAPE_THEN_GENERATE
        if research:
            return ProcessingPath.RESEARCH_THEN_GENERATE

        return ProcessingPath.DIRECT_GENERATE

    def _estimate_complexity(
        self,
        inputs: List[ContentInput],
        duration: int,
        needs_transcription: bool
    ) -> Literal["simple", "moderate", "complex"]:
        """Estimate processing complexity"""
        score = 0

        # Number of inputs
        score += len(inputs) * 2

        # Duration factor
        if duration > 30:
            score += 3
        elif duration > 15:
            score += 2
        elif duration > 5:
            score += 1

        # Transcription adds complexity
        if needs_transcription:
            score += 3

        # Multiple content types
        types = set(i.content_type for i in inputs)
        if len(types) > 1:
            score += 2

        if score >= 8:
            return "complex"
        elif score >= 4:
            return "moderate"
        return "simple"

    def _extract_topics(
        self,
        request: str,
        inputs: List[ContentInput]
    ) -> List[str]:
        """Extract likely topics from request and inputs"""
        topics = []

        # Simple keyword extraction (could use LLM for better results)
        # Look for quoted phrases
        quoted = re.findall(r'"([^"]+)"', request)
        topics.extend(quoted)

        # Look for "about X" patterns
        about = re.findall(r'about\s+([^,.]+)', request, re.IGNORECASE)
        topics.extend(about)

        # Add topic-type inputs directly
        for inp in inputs:
            if inp.content_type == ContentType.TOPIC:
                topics.append(inp.source)

        # Deduplicate and clean
        seen = set()
        unique = []
        for t in topics:
            t_clean = t.strip().lower()
            if t_clean and t_clean not in seen:
                seen.add(t_clean)
                unique.append(t.strip())

        return unique[:5]  # Limit to 5 topics

    def _detect_language(self, request: str, target: str) -> str:
        """Detect language from request or use target"""
        # Simple detection based on common words
        hindi_markers = ["में", "का", "है", "और", "को"]
        tamil_markers = ["என்", "இது", "மற்றும்", "ஒரு"]

        for marker in hindi_markers:
            if marker in request:
                return "hindi"

        for marker in tamil_markers:
            if marker in request:
                return "tamil"

        return target.lower()

    def _generate_warnings(
        self,
        inputs: List[ContentInput],
        duration: int
    ) -> List[str]:
        """Generate warnings about potential issues"""
        warnings = []

        # Check for missing files
        for inp in inputs:
            if inp.content_type in (ContentType.DOCUMENT, ContentType.AUDIO, ContentType.VIDEO):
                if not os.path.exists(inp.source) and not inp.source.startswith("http"):
                    warnings.append(f"File not found: {inp.source}")

        # Duration warnings
        if duration > 45:
            warnings.append(
                "Long duration (>45min) may take significant time to generate "
                "and requires more source material"
            )

        # YouTube warnings
        for inp in inputs:
            if inp.content_type == ContentType.VIDEO and "youtube" in inp.source.lower():
                warnings.append(
                    "YouTube transcription depends on available captions or "
                    "will require audio extraction"
                )

        return warnings

    def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        LangGraph-compatible process method

        Expected state keys:
            - user_request: str
            - contents: List[Dict[str, str]]
            - target_language: str
            - target_duration_minutes: int

        Returns updated state with:
            - routing_decision: RoutingDecision
            - next_agent: str (name of next agent to invoke)
        """
        user_request = state.get("user_request", "")
        contents = state.get("contents", [])
        target_language = state.get("target_language", "english")
        target_duration = state.get("target_duration_minutes", 10)

        decision = self.route(
            user_request=user_request,
            contents=contents,
            target_language=target_language,
            target_duration=target_duration
        )

        # Determine next agent based on path
        next_agent = self._get_next_agent(decision)

        return {
            **state,
            "routing_decision": decision,
            "content_types": [i.content_type.value for i in decision.inputs],
            "topics": decision.topics_identified,
            "language": decision.language_detected,
            "complexity": decision.estimated_complexity,
            "next_agent": next_agent,
            "warnings": decision.warnings
        }

    def _get_next_agent(self, decision: RoutingDecision) -> str:
        """Determine which agent to invoke next"""
        path = decision.primary_path

        if path == ProcessingPath.TRANSCRIBE_THEN_GENERATE:
            return "content_gatherer"  # Will handle transcription
        if path == ProcessingPath.EXTRACT_THEN_GENERATE:
            return "content_gatherer"  # Will handle extraction
        if path == ProcessingPath.SCRAPE_THEN_GENERATE:
            return "content_gatherer"  # Will handle scraping
        if path == ProcessingPath.RESEARCH_THEN_GENERATE:
            return "content_gatherer"  # Will handle research
        if path == ProcessingPath.MULTI_SOURCE:
            return "content_gatherer"  # Handles all
        return "script_generator"  # Direct generation

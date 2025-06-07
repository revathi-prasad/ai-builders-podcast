"""
Data models for the AI Builders Podcast System
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from config import Language, EpisodeType

@dataclass
class EpisodeContext:
    """Configuration for episode generation
    
    Args:
        topic: Main topic of the episode
        primary_language: Language in which the episode will be primarily created
        secondary_languages: Languages for which summaries or adaptations will be created
        episode_type: Type of episode (build, introduction, conversation, etc.)
        target_duration: Target duration in minutes
        cost_tier: Quality and cost tier ("economy", "standard", "premium")
        cultural_focus: Cultural focus of the episode (e.g., "startup_ecosystem")
        episode_number: Episode number in the series
        include_intro: Whether to include standard intro
        include_outro: Whether to include standard outro
        transcript_only: Generate only transcript without audio
        use_transcript: Path to pre-defined transcript file
        reference_material: Path to reference material for content enrichment
    """
    topic: str
    primary_language: Language
    secondary_languages: List[Language]
    episode_type: EpisodeType
    target_duration: int  # minutes
    cost_tier: str        # "economy", "standard", "premium"
    cultural_focus: str   # e.g., "startup_ecosystem", "traditional_business"
    episode_number: int = 0
    include_intro: bool = True
    include_outro: bool = True
    transcript_only: bool = False  # When True, skip audio generation
    use_transcript: Optional[str] = None  # Path to a pre-defined transcript file
    reference_material: Optional[str] = None  # Path to reference material
    preserve_standard_sections: bool = False  # When True, preserve standard intros/outros during transformation

@dataclass
class DialogueSegment:
    """A segment of dialogue in a podcast episode
    
    Args:
        speaker: Speaker identifier (e.g., "ALEX", "MAYA")
        text: Text content of the dialogue
        timestamp: Sequence position in the episode
        metadata: Additional metadata (e.g., emotion, emphasis)
    """
    speaker: str
    text: str
    timestamp: int
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResearchCitation:
    """Citation information for research sources
    
    Args:
        source: Name of the source (e.g., "Research Paper Title")
        url: URL of the source
        access_date: Date the source was accessed
        content_snippet: Relevant snippet from the source
        author: Author of the source
        publication_date: Publication date of the source
        source_type: Type of source (e.g., "academic_paper", "website")
    """
    source: str
    url: str
    access_date: datetime
    content_snippet: str
    author: Optional[str] = None
    publication_date: Optional[str] = None
    source_type: Optional[str] = None
    
    def format_citation(self, style: str = "APA") -> str:
        """Format the citation according to the specified style
        
        Args:
            style: Citation style (e.g., "APA", "MLA")
            
        Returns:
            Formatted citation string
        """
        if style == "APA":
            if self.author and self.publication_date:
                return f"{self.author} ({self.publication_date}). {self.source}. Retrieved from {self.url} on {self.access_date.strftime('%B %d, %Y')}."
            else:
                return f"{self.source}. Retrieved from {self.url} on {self.access_date.strftime('%B %d, %Y')}."
        elif style == "MLA":
            if self.author and self.publication_date:
                return f"{self.author}. \"{self.source}.\" {self.publication_date}, {self.url}. Accessed {self.access_date.strftime('%d %B %Y')}."
            else:
                return f"\"{self.source}.\" {self.url}. Accessed {self.access_date.strftime('%d %B %Y')}."
        else:
            return f"{self.source} - {self.url} (Accessed: {self.access_date.strftime('%Y-%m-%d')})"

@dataclass
class ResearchResult:
    """Results of research on a topic
    
    Args:
        topic: Research topic
        summary: Summary of research findings
        key_points: Key points extracted from research
        citations: Citations of sources
        examples: Examples relevant to the topic
        regional_insights: Region-specific insights
        custom_documents: Information about custom documents used
    """
    topic: str
    summary: str
    key_points: List[str]
    citations: List[ResearchCitation]
    examples: List[str]
    regional_insights: Dict[str, List[str]]
    custom_documents: Optional[Dict[str, Any]] = None
    
    def to_markdown(self) -> str:
        """Convert research results to markdown format
        
        Returns:
            Markdown formatted research results
        """
        markdown = f"# Research: {self.topic}\n\n"
        markdown += f"## Summary\n\n{self.summary}\n\n"
        
        markdown += "## Key Points\n\n"
        for point in self.key_points:
            markdown += f"- {point}\n"
        markdown += "\n"
        
        markdown += "## Examples\n\n"
        for example in self.examples:
            markdown += f"- {example}\n"
        markdown += "\n"
        
        markdown += "## Regional Insights\n\n"
        for region, insights in self.regional_insights.items():
            markdown += f"### {region.capitalize()}\n\n"
            for insight in insights:
                markdown += f"- {insight}\n"
            markdown += "\n"
        
        if self.custom_documents:
            markdown += "## Custom Documents\n\n"
            for doc_name, doc_info in self.custom_documents.items():
                markdown += f"### {doc_name}\n\n"
                markdown += f"- Type: {doc_info.get('type', 'Unknown')}\n"
                markdown += f"- Key insights: {doc_info.get('insights_count', 0)}\n"
                if 'summary' in doc_info:
                    markdown += f"\n{doc_info['summary']}\n\n"
        
        markdown += "## Sources\n\n"
        for i, citation in enumerate(self.citations, 1):
            markdown += f"{i}. {citation.format_citation()}\n"
        
        return markdown

@dataclass
class TransformationResult:
    """Result of transforming content between languages
    
    Args:
        original_language: Original language of the content
        target_language: Target language for transformation
        original_content: Original content
        transformed_content: Transformed content
        regional_adaptations: List of regional adaptations made
        terminology_mappings: Mapping of terminology between languages
    """
    original_language: Language
    target_language: Language
    original_content: List[DialogueSegment]
    transformed_content: List[DialogueSegment]
    regional_adaptations: List[str]
    terminology_mappings: Dict[str, str]

@dataclass
class EpisodeResult:
    """Result of episode generation
    
    Args:
        dialogue: List of dialogue segments
        audio_file: Path to the generated audio file
        transcript: Formatted transcript text
        research: Research results used in the episode
        transformations: List of transformations to other languages
        metadata: Additional metadata about the episode
    """
    dialogue: List[DialogueSegment]
    audio_file: Optional[str]
    transcript: str
    research: Optional[ResearchResult] = None
    transformations: List[TransformationResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

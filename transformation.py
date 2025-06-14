"""
Language transformation module for the AI Builders Podcast System

This module handles the transformation of content between languages, adapting
not just the language but also the cultural context and examples.
"""

import hashlib
import json
import logging
import re
import time
from typing import Dict, List, Optional, Any, Tuple

import anthropic

from config import ConstellationConfig, Language
from models import DialogueSegment, TransformationResult
from cache import IntelligentCache

class TransformationEngine:
    """
    Engine for transforming content between languages
    
    This class handles the transformation of podcast content from one language
    to another, while adapting cultural context and examples.
    
    Attributes:
        cache: Instance of IntelligentCache for caching transformations
        claude_client: Anthropic Claude client
    """
    
    def __init__(self, cache: IntelligentCache):
        """Initialize the transformation engine
        
        Args:
            cache: Instance of IntelligentCache for caching transformations
        """
        self.cache = cache
        self.claude_client = anthropic.Anthropic(api_key=ConstellationConfig.CLAUDE_API_KEY)
    
    def transform_content(self, original_segments: List[DialogueSegment], 
                    source_language: Language, target_language: Language,
                    topic: str, cost_tier: str = "standard",
                    reference_material: Optional[str] = None,
                    preserve_standard_sections: bool = False) -> TransformationResult:
        """Transform content from one language to another
        
        Args:
            original_segments: List of dialogue segments in the source language
            source_language: Source language
            target_language: Target language
            topic: Topic of the content
            cost_tier: Cost tier for Claude API
            reference_material: Optional reference material to enrich the transformation
            preserve_standard_sections: Whether to preserve standard intro/outro sections
            
        Returns:
            TransformationResult object containing the transformed content
        """
        # Check if we already have a cached transformation
        original_content_str = json.dumps([{
            "speaker": s.speaker,
            "text": s.text,
            "timestamp": s.timestamp
        } for s in original_segments])
        
        cached_result = self.cache.get_cached_transformation(
            source_language.value, 
            target_language.value,
            original_content_str
        )
        
        if cached_result:
            # Convert the cached string back to a TransformationResult
            cached_segments = json.loads(cached_result)
            transformed_segments = [
                DialogueSegment(
                    speaker=s["speaker"],
                    text=s["text"],
                    timestamp=s["timestamp"],
                    metadata=s.get("metadata", {})
                )
                for s in cached_segments
            ]
            
            # Create a simple TransformationResult with limited info since we don't cache everything
            return TransformationResult(
                original_language=source_language,
                target_language=target_language,
                original_content=original_segments,
                transformed_content=transformed_segments,
                regional_adaptations=[],
                terminology_mappings={}
            )
        
        # If preserving standard sections, process differently
        if preserve_standard_sections:
            return self._transform_with_preserved_sections(
                original_segments,
                source_language,
                target_language,
                topic,
                cost_tier,
                reference_material
            )
        
        # Get transformation guidelines for target language
        if target_language.value not in ConstellationConfig.TRANSFORMATION_GUIDELINES:
            raise ValueError(f"No transformation guidelines available for {target_language.value}")
        
        guidelines = ConstellationConfig.TRANSFORMATION_GUIDELINES[target_language.value]
        principles = "\n".join([f"{i+1}. {p}" for i, p in enumerate(guidelines["principles"])])
        
        # Create terminology mapping table
        terminology_table = "\n".join([
            f"| {term} | {translation} |" 
            for term, translation in guidelines["terminology"].items()
        ])
        
        # Get regional examples for target language
        regional_examples = ""
        if target_language.value in ConstellationConfig.REGIONAL_EXAMPLES:
            examples = ConstellationConfig.REGIONAL_EXAMPLES[target_language.value]
            regional_examples = "\n".join([
                f"- {concept}: {example}" 
                for concept, example in examples.items()
            ])
        
        # Format the content segments for Claude
        formatted_original = "\n\n".join([
            f"{segment.speaker}: {segment.text}" 
            for segment in original_segments
        ])
        
        # Prepare reference material if provided
        reference_material_text = ""
        if reference_material:
            reference_material_text = f"""
## Reference Material
This additional material may help enrich the transformation:

{reference_material}

Use concepts, examples, and flow from this reference material where appropriate to enhance the transformation.
"""
        
        # Create the prompt for Claude
        model = ConstellationConfig.CLAUDE_MODELS[cost_tier]

        # Add casual conversation guidelines
        casual_guidelines = ""
        if target_language.value == "hindi":
            casual_guidelines = """
        🇮🇳 **HINDI CASUAL CONVERSATION STYLE:**
        - बोलचाल की हिंदी का इस्तेमाल करें - जैसे chai पर दोस्तों से बात करते हैं
        - कठिन संस्कृत शब्दों से बचें, आसान रोज़ाना के शब्द इस्तेमाल करें  
        - न्यूज़ चैनल की भाषा बिल्कुल न करें - YouTube vlog की तरह बोलें
        - "ये तो मज़ेदार है!" जैसे expressions use करें
        - Bollywood, daily life के examples दें
        - natural sound करना चाहिए
        """
        elif target_language.value == "tamil":
            casual_guidelines = """
        🇮🇳 **TAMIL CASUAL CONVERSATION STYLE:**
        - சாதாரண பேச்சு தமிழ் - filter coffee அடிக்கும்போது நண்பர்களிடம் பேசுவது போல
        - Literary words வேண்டாம் - daily use பண்ற words பயன்படுத்துங்க
        - News reader மாதிரி பேசாதீங்க - casual podcast மாதிரி பேசுங்க
        - Cinema, அன்றாட வாழ்க்கை examples கொடுங்க
        - natural-ஆ கேக்கணும்
        """

        # Get casual replacements
        casual_replacements = ""
        if "casual_replacements" in guidelines:
            casual_replacements = "\n### ❌ Avoid → ✅ Use Instead:\n"
            for formal, casual in guidelines["casual_replacements"].items():
                casual_replacements += f"❌ {formal} → ✅ {casual}\n"
        
        prompt = f"""
# Content Transformation Task

PRIMARY GOAL: Make this sound like friends chatting casually!
{casual_guidelines}

## Original Content ({source_language.value})
Topic: {topic}

{formatted_original}

## Transformation Guidelines for {target_language.value}
Style: {guidelines["style"]}

### Principles:
{principles}

{casual_replacements}

### Terminology Mapping:
| English Term | {target_language.value} Term |
|------------|--------------|
{terminology_table}

### Regional Examples:
{regional_examples}

{reference_material_text}

## Instructions
1. Transform the content from {source_language.value} to {target_language.value} following the guidelines above.
2. Maintain the speaker turns and overall flow of the conversation.
3. Adapt examples and references to be culturally relevant to {target_language.value} speakers.
4. Use the specified terminology for technical terms.
5. CONVERSATIONAL TONE: Sound like two friends excitedly discussing AI over coffee/chai/tea
6. MODERN LANGUAGE: Use words people actually say in real life - like YouTube vlogs or WhatsApp voice messages
7. CULTURAL REFERENCES: Include local examples, movies, daily life that people relate to
8. SHORT & NATURAL: Keep sentences flowing and natural - don't worry about perfect grammar
9. REAL SPEECH: Use expressions people actually say, not formal written language
10. Format your output as:
   SPEAKER: Transformed text

Remember this is not a direct translation but a cultural adaptation. The goal is to convey the same information and insights in a way that feels natural and relevant to {target_language.value} speakers.

## Output Format
Transform each segment keeping the casual, friendly conversation style, but adapting the content appropriately for {target_language.value} speakers:

Remember: This should sound like a fun conversation between 2 intelligent AI-Hosts passionate about the purpose of this podcast and the impact of AI, NOT a news report or textbook!
"""
        
        try:
            # Call Claude for transformation
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=16000,  # Increased from default to handle longer content
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            transformed_text = response.content[0].text
            
            # Parse the transformed content
            transformed_segments = self._parse_transformed_content(
                transformed_text, original_segments
            )
            
            # Extract regional adaptations made (simplified implementation)
            regional_adaptations = self._extract_regional_adaptations(
                transformed_text, target_language.value
            )
            
            # Create the transformation result
            result = TransformationResult(
                original_language=source_language,
                target_language=target_language,
                original_content=original_segments,
                transformed_content=transformed_segments,
                regional_adaptations=regional_adaptations,
                terminology_mappings=guidelines["terminology"]
            )
            
            # Cache the transformation
            transformed_content_str = json.dumps([{
                "speaker": s.speaker,
                "text": s.text,
                "timestamp": s.timestamp,
                "metadata": s.metadata
            } for s in transformed_segments])
            
            self.cache.cache_transformation(
                source_language.value, 
                target_language.value,
                original_content_str,
                transformed_content_str
            )
            
            return result
            
        except Exception as e:
            logging.error(f"Error transforming content: {e}")
            # Return a simple transformation result with original content
            return TransformationResult(
                original_language=source_language,
                target_language=target_language,
                original_content=original_segments,
                transformed_content=original_segments,  # Just return original content on error
                regional_adaptations=[f"Error during transformation: {str(e)}"],
                terminology_mappings={}
            )
    
    def _transform_with_preserved_sections(self, original_segments: List[DialogueSegment],
                                     source_language: Language, target_language: Language,
                                     topic: str, cost_tier: str = "standard",
                                     reference_material: Optional[str] = None) -> TransformationResult:
        """Transform content while preserving standard sections"""
        # Create cache key for original content
        original_content_str = json.dumps([{
            "speaker": s.speaker,
            "text": s.text,
            "timestamp": s.timestamp
        } for s in original_segments])
        
        # Check cache first
        cached_result = self.cache.get_cached_transformation(
            source_language.value, 
            target_language.value,
            original_content_str
        )
        
        if cached_result:
            # Convert cached string back to TransformationResult
            cached_segments = json.loads(cached_result)
            transformed_segments = [
                DialogueSegment(
                    speaker=s["speaker"],
                    text=s["text"],
                    timestamp=s["timestamp"],
                    metadata=s.get("metadata", {})
                )
                for s in cached_segments
            ]
            
            return TransformationResult(
                original_language=source_language,
                target_language=target_language,
                original_content=original_segments,
                transformed_content=transformed_segments,
                regional_adaptations=[],
                terminology_mappings={}
            )
        
        # Identify intro and outro segments
        standard_sections = self._simple_detect_sections(original_segments)
        standard_intro_indices = standard_sections["intro"]
        standard_outro_indices = standard_sections["outro"]
        
        # Extract content segments (everything that's not intro or outro)
        all_indices = set(range(len(original_segments)))
        standard_indices = set(standard_intro_indices + standard_outro_indices)
        content_indices = sorted(list(all_indices - standard_indices))
        
        # Get only the content segments for transformation
        content_segments = [original_segments[i] for i in content_indices]
        
        logging.info(f"Transforming {len(content_segments)} content segments " 
                    f"from {source_language.value} to {target_language.value}")
        
        # Get transformation guidelines
        if target_language.value not in ConstellationConfig.TRANSFORMATION_GUIDELINES:
            raise ValueError(f"No transformation guidelines available for {target_language.value}")
        
        guidelines = ConstellationConfig.TRANSFORMATION_GUIDELINES[target_language.value]
        principles = "\n".join([f"{i+1}. {p}" for i, p in enumerate(guidelines["principles"])])
        
        # Create terminology mapping table
        terminology_table = "\n".join([
            f"| {term} | {translation} |" 
            for term, translation in guidelines["terminology"].items()
        ])
        
        # Get regional examples
        regional_examples = ""
        if target_language.value in ConstellationConfig.REGIONAL_EXAMPLES:
            examples = ConstellationConfig.REGIONAL_EXAMPLES[target_language.value]
            regional_examples = "\n".join([
                f"- {concept}: {example}" 
                for concept, example in examples.items()
            ])
        
        # Get source and target podcast titles
        source_podcast_title = self.localize_podcast_title(source_language)
        target_podcast_title = self.localize_podcast_title(target_language)
        
        # Get speaker mapping
        speaker_mapping = self._get_speaker_mapping(source_language, target_language)
        speaker_mapping_text = "\n".join([
            f"- Replace '{source}' with '{target}' consistently" 
            for source, target in speaker_mapping.items()
        ])
        
        # Format content segments
        formatted_original = "\n\n".join([
            f"{segment.speaker}: {segment.text}" 
            for segment in content_segments
        ])
        
        # Prepare reference material
        reference_material_text = ""
        if reference_material:
            reference_material_text = f"""
    ## Reference Material
    {reference_material}
    """
        model = ConstellationConfig.CLAUDE_MODELS[cost_tier]
        
        # Create prompt with explicit instructions about podcast title and hosts
        prompt = f"""
    # Content Transformation Task

    ## Original Content ({source_language.value})
    Topic: {topic}

    {formatted_original}

    ## Critical Transformation Requirements
    1. ALWAYS replace the podcast title "{source_podcast_title}" with "{target_podcast_title}" EVERYWHERE it appears
    2. ALWAYS replace host names as follows:
    {speaker_mapping_text}
    3. Adapt any personal anecdotes or background stories to match the target language hosts' personalities
    4. Replace regional references with ones relevant to {target_language.value}-speaking regions

    ## Transformation Guidelines for {target_language.value}
    Style: {guidelines["style"]}

    ### Principles:
    {principles}

    ### Terminology Mapping:
    | English Term | {target_language.value} Term |
    |------------|--------------|
    {terminology_table}

    ### Regional Examples:
    {regional_examples}

    {reference_material_text}

    ## Output Format
    Transform each segment while adapting the content appropriately for {target_language.value} speakers.
    Maintain speaker turns, but use the target language host names consistently.
    """
        
        try:
            # Call Claude for transformation
            logging.info(f"Calling Claude API to transform content...")
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=16000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            transformed_text = response.content[0].text
            logging.info(f"Received transformation response ({len(transformed_text)} chars)")
            
            # Manually apply speaker mapping to ensure consistency
            for source_speaker, target_speaker in speaker_mapping.items():
                # Replace the speaker labels at the start of lines
                transformed_text = re.sub(
                    fr"^{source_speaker}:", 
                    f"{target_speaker}:", 
                    transformed_text, 
                    flags=re.MULTILINE
                )
                
                # Also replace podcast title mentions to ensure consistency
                transformed_text = transformed_text.replace(
                    source_podcast_title, 
                    target_podcast_title
                )
            
            # Parse transformed content
            transformed_content_segments = self._parse_transformed_content(
                transformed_text, content_segments
            )
            
            # Extract regional adaptations
            regional_adaptations = self._extract_regional_adaptations(
                transformed_text, target_language.value
            )
            
            # Get standard intro and outro for target language
            target_intro = self.get_language_intro(target_language)
            target_outro = self.get_language_outro(target_language)
            
            # Parse standard sections
            target_intro_segments = self._parse_standard_section(target_intro)
            target_outro_segments = self._parse_standard_section(target_outro)
            
            # Combine into final segments
            final_segments = []
            
            # Add intro segments
            timestamp = 0
            for segment in target_intro_segments:
                segment.timestamp = timestamp
                final_segments.append(segment)
                timestamp += 1
            
            # Add transformed content segments with corrected speakers
            for segment in transformed_content_segments:
                # Apply speaker mapping again to ensure consistency
                if segment.speaker in speaker_mapping:
                    segment.speaker = speaker_mapping[segment.speaker]
                segment.timestamp = timestamp
                final_segments.append(segment)
                timestamp += 1
            
            # Add outro segments
            for segment in target_outro_segments:
                segment.timestamp = timestamp
                final_segments.append(segment)
                timestamp += 1
            
            # Create transformation result
            result = TransformationResult(
                original_language=source_language,
                target_language=target_language,
                original_content=original_segments,
                transformed_content=final_segments,
                regional_adaptations=regional_adaptations,
                terminology_mappings=guidelines["terminology"]
            )
            
            # Cache the result
            transformed_content_str = json.dumps([{
                "speaker": s.speaker,
                "text": s.text,
                "timestamp": s.timestamp,
                "metadata": getattr(s, 'metadata', {})
            } for s in final_segments])
            
            self.cache.cache_transformation(
                source_language.value, 
                target_language.value,
                original_content_str,
                transformed_content_str
            )
            
            return result
            
        except Exception as e:
            logging.error(f"Error transforming content: {e}")
            return TransformationResult(
                original_language=source_language,
                target_language=target_language,
                original_content=original_segments,
                transformed_content=original_segments,
                regional_adaptations=[f"Error: {str(e)}"],
                terminology_mappings={}
            )

    def _post_process_transformed_content(self, 
                                   segments: List[DialogueSegment],
                                   source_language: Language, 
                                   target_language: Language) -> List[DialogueSegment]:
        """Apply final post-processing to ensure consistency
        
        Args:
            segments: Transformed segments
            source_language: Source language
            target_language: Target language
            
        Returns:
            Post-processed segments
        """
        # Get speaker mapping
        speaker_mapping = self._get_speaker_mapping(source_language, target_language)
        
        # Get podcast titles
        source_title = self.localize_podcast_title(source_language)
        target_title = self.localize_podcast_title(target_language)
        
        # Process each segment
        for segment in segments:
            # Apply speaker mapping
            if segment.speaker in speaker_mapping:
                segment.speaker = speaker_mapping[segment.speaker]
            
            # Replace podcast title in the text
            if source_title in segment.text:
                segment.text = segment.text.replace(source_title, target_title)
        
        return segments

    def _verify_transformation(self, segments: List[DialogueSegment], 
                        source_language: Language, 
                        target_language: Language) -> Dict[str, Any]:
        """Verify transformation for quality issues
        
        Args:
            segments: Transformed segments
            source_language: Source language
            target_language: Target language
            
        Returns:
            Dictionary with verification results
        """
        issues = []
        
        # Get speaker mapping
        speaker_mapping = self._get_speaker_mapping(source_language, target_language)
        source_speakers = list(speaker_mapping.keys())
        target_speakers = list(speaker_mapping.values())
        
        # Get podcast titles
        source_title = self.localize_podcast_title(source_language)
        target_title = self.localize_podcast_title(target_language)
        
        # Check each segment
        for i, segment in enumerate(segments):
            # Check for incorrect speakers
            if segment.speaker in source_speakers:
                issues.append(f"Segment {i}: Found source speaker {segment.speaker} instead of target speaker")
            
            # Check for source podcast title
            if source_title in segment.text:
                issues.append(f"Segment {i}: Found source podcast title '{source_title}' instead of '{target_title}'")
        
        # Log issues
        if issues:
            logging.warning(f"Found {len(issues)} issues in transformation:")
            for issue in issues:
                logging.warning(f"  - {issue}")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }   
    
    def _get_speaker_mapping(self, source_language: Language, target_language: Language) -> Dict[str, str]:
        """Get speaker mapping from source to target language
        
        Args:
            source_language: Source language
            target_language: Target language
            
        Returns:
            Dictionary mapping source speakers to target speakers
        """
        # Get voice library speakers
        source_hosts = list(ConstellationConfig.VOICE_LIBRARY[source_language.value].keys())
        target_hosts = list(ConstellationConfig.VOICE_LIBRARY[target_language.value].keys())
        
        # Create mapping (uppercase for matching in the text)
        mapping = {}
        for i in range(min(len(source_hosts), len(target_hosts))):
            mapping[source_hosts[i].upper()] = target_hosts[i].upper()
        
        logging.info(f"Speaker mapping: {mapping}")
        return mapping

    def _transform_content_in_chunks(self, content_segments: List[DialogueSegment],
                                  source_language: Language, target_language: Language,
                                  topic: str, cost_tier: str = "standard",
                                  reference_material: Optional[str] = None,
                                  chunk_size: int = 10) -> TransformationResult:
        """Transform content in smaller chunks for very long content
        
        Args:
            content_segments: Content segments to transform
            source_language: Source language
            target_language: Target language
            topic: Topic of the content
            cost_tier: Cost tier for Claude API
            reference_material: Optional reference material
            chunk_size: Size of each chunk
            
        Returns:
            TransformationResult with combined chunks
        """
        logging.info(f"Content too long, transforming in chunks of {chunk_size}")
        
        # Split content into smaller chunks
        chunks = []
        for i in range(0, len(content_segments), chunk_size):
            chunks.append(content_segments[i:i+chunk_size])
        
        # Transform each chunk
        transformed_chunks = []
        for i, chunk in enumerate(chunks):
            logging.info(f"Transforming chunk {i+1}/{len(chunks)}...")
            
            # Get transformation guidelines for target language
            if target_language.value not in ConstellationConfig.TRANSFORMATION_GUIDELINES:
                raise ValueError(f"No transformation guidelines available for {target_language.value}")
            
            guidelines = ConstellationConfig.TRANSFORMATION_GUIDELINES[target_language.value]
            principles = "\n".join([f"{i+1}. {p}" for i, p in enumerate(guidelines["principles"])])
            
            # Create terminology mapping table
            terminology_table = "\n".join([
                f"| {term} | {translation} |" 
                for term, translation in guidelines["terminology"].items()
            ])
            
            # Format the chunk for Claude
            formatted_chunk = "\n\n".join([
                f"{segment.speaker}: {segment.text}" 
                for segment in chunk
            ])
            
            # Create the prompt for Claude
            model = ConstellationConfig.CLAUDE_MODELS[cost_tier]
            
            prompt = f"""
# Content Transformation Task - Chunk {i+1}/{len(chunks)}

## Original Content ({source_language.value})
Topic: {topic}

{formatted_chunk}

## Transformation Guidelines for {target_language.value}
Style: {guidelines["style"]}

### Principles:
{principles}

### Terminology Mapping:
| English Term | {target_language.value} Term |
|------------|--------------|
{terminology_table}

## Instructions
1. Transform the content from {source_language.value} to {target_language.value} following the guidelines above.
2. Maintain the speaker turns and overall flow of the conversation.
3. Adapt examples and references to be culturally relevant to {target_language.value} speakers.
4. Use the specified terminology for technical terms.
5. Format your output as:
   SPEAKER: Transformed text

Remember this is not a direct translation but a cultural adaptation. The goal is to convey the same information and insights in a way that feels natural and relevant to {target_language.value} speakers.
"""
            
            try:
                # Call Claude for transformation
                response = self.claude_client.messages.create(
                    model=model,
                    max_tokens=16000,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                transformed_text = response.content[0].text
                
                # Parse the transformed content
                transformed_segments = self._parse_transformed_content(
                    transformed_text, chunk
                )
                
                # Add to transformed chunks
                transformed_chunks.extend(transformed_segments)
                
                # Add a small delay to avoid rate limits
                time.sleep(1)
                
            except Exception as e:
                logging.error(f"Error transforming chunk {i+1}: {e}")
                # Use original chunk as fallback
                transformed_chunks.extend(chunk)
        
        # Get standard intro and outro for target language
        target_intro = self.get_language_intro(target_language)
        target_outro = self.get_language_outro(target_language)
        
        # Parse standard intro and outro for target language
        target_intro_segments = self._parse_standard_section(target_intro)
        target_outro_segments = self._parse_standard_section(target_outro)
        
        # Combine into final segments
        final_segments = []
        
        # Add intro segments
        timestamp = 0
        for segment in target_intro_segments:
            segment.timestamp = timestamp
            final_segments.append(segment)
            timestamp += 1
        
        # Add transformed content segments
        for segment in transformed_chunks:
            segment.timestamp = timestamp
            final_segments.append(segment)
            timestamp += 1
        
        # Add outro segments
        for segment in target_outro_segments:
            segment.timestamp = timestamp
            final_segments.append(segment)
            timestamp += 1
        
        # Create the transformation result
        result = TransformationResult(
            original_language=source_language,
            target_language=target_language,
            original_content=content_segments,
            transformed_content=final_segments,
            regional_adaptations=["Content transformed in chunks due to length"],
            terminology_mappings=guidelines["terminology"]
        )
        
        return result
    
    def _parse_standard_section(self, section_text: str) -> List[DialogueSegment]:
        """Parse a standard section (intro or outro) into DialogueSegment objects
        
        Args:
            section_text: Text of the standard section
            
        Returns:
            List of DialogueSegment objects
        """
        segments = []
        timestamp = 0
        
        for part in section_text.split("\n\n"):
            part = part.strip()
            if not part:
                continue
                
            if part.startswith("[INTRO MUSIC]") or part.startswith("[OUTRO MUSIC]"):
                segments.append(DialogueSegment(
                    speaker="MUSIC",
                    text=part,
                    timestamp=timestamp
                ))
                timestamp += 1
            elif ":" in part:
                speaker, text = part.split(":", 1)
                segments.append(DialogueSegment(
                    speaker=speaker.strip(),
                    text=text.strip(),
                    timestamp=timestamp
                ))
                timestamp += 1
        
        return segments
    
    def _simple_detect_sections(self, segments: List[DialogueSegment]) -> Dict[str, List[int]]:
        """Simplified detection of intro and outro sections
        
        Args:
            segments: List of dialogue segments
            
        Returns:
            Dictionary with indices of intro and outro segments
        """
        results = {"intro": [], "outro": []}
        
        # Look for music markers
        intro_found = False
        outro_found = False
        
        for i, segment in enumerate(segments):
            # Check for intro music
            if segment.speaker == "MUSIC" and segment.text == "[INTRO MUSIC]" and not intro_found:
                intro_found = True
                # Mark this and next few segments as intro (up to 10 segments)
                for j in range(i, min(i + 10, len(segments))):
                    results["intro"].append(j)
                    # Stop if we hit another music marker
                    if j > i and segments[j].speaker == "MUSIC":
                        break
            
            # Check for outro music
            if segment.speaker == "MUSIC" and segment.text == "[OUTRO MUSIC]" and not outro_found:
                outro_found = True
                # Mark this and previous few segments as outro (up to 10 segments)
                for j in range(max(0, i - 9), i + 1):
                    results["outro"].append(j)
                    # Stop if we hit another music marker before this one
                    if j < i and segments[j].speaker == "MUSIC":
                        results["outro"] = [k for k in results["outro"] if k >= j]
                        break
        
        # If no intro/outro found with music markers, use position-based detection
        if not intro_found:
            # Assume first 5 segments are intro
            results["intro"] = list(range(min(5, len(segments))))
        
        if not outro_found:
            # Assume last 5 segments are outro
            results["outro"] = list(range(max(0, len(segments) - 5), len(segments)))
        
        # Clean up any overlap (intro and outro should not overlap)
        intro_set = set(results["intro"])
        outro_set = set(results["outro"])
        overlap = intro_set.intersection(outro_set)
        
        if overlap:
            # Remove overlap from intro if it's in the second half of the segments
            midpoint = len(segments) // 2
            for idx in overlap:
                if idx >= midpoint:
                    results["intro"].remove(idx)
                else:
                    results["outro"].remove(idx)
        
        return results
    
    def _parse_transformed_content(self, transformed_text: str, 
                                original_segments: List[DialogueSegment]) -> List[DialogueSegment]:
        """Parse the transformed content from Claude's response
        
        Args:
            transformed_text: Transformed text from Claude
            original_segments: Original dialogue segments
            
        Returns:
            List of transformed dialogue segments
        """
        transformed_segments = []
        lines = transformed_text.strip().split('\n')
        
        # Map to track which speakers we've processed
        speaker_map = {}
        for segment in original_segments:
            speaker_map[segment.speaker] = True
        
        # Parse the transformed content
        current_speaker = None
        current_text = []
        timestamp = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if this line starts with a speaker identifier
            speaker_match = False
            for speaker in speaker_map.keys():
                if line.upper().startswith(f"{speaker}:"):
                    # If we already have a speaker, add the previous segment
                    if current_speaker and current_text:
                        transformed_segments.append(DialogueSegment(
                            speaker=current_speaker,
                            text=" ".join(current_text),
                            timestamp=timestamp,
                            metadata={}
                        ))
                        timestamp += 1
                        current_text = []
                    
                    # Set the new speaker and text
                    current_speaker = speaker
                    current_text = [line[line.find(":")+1:].strip()]
                    speaker_match = True
                    break
            
            # If this line doesn't start with a speaker, add it to the current text
            if not speaker_match and current_speaker:
                current_text.append(line)
        
        # Add the last segment
        if current_speaker and current_text:
            transformed_segments.append(DialogueSegment(
                speaker=current_speaker,
                text=" ".join(current_text),
                timestamp=timestamp,
                metadata={}
            ))
        
        # If we couldn't parse any segments, use a simple approach
        if not transformed_segments:
            # Split by possible speaker identifiers
            segments = re.split(r'\n\s*([A-Z]+):\s*', transformed_text)
            if len(segments) > 1:
                # First element is empty or intro text, skip it
                segments = segments[1:]
                
                # Process pairs of speaker and text
                for i in range(0, len(segments), 2):
                    if i+1 < len(segments):
                        speaker = segments[i]
                        text = segments[i+1].strip()
                        
                        # Find the matching original speaker
                        for orig_speaker in speaker_map.keys():
                            if orig_speaker.upper() == speaker.upper():
                                transformed_segments.append(DialogueSegment(
                                    speaker=orig_speaker,
                                    text=text,
                                    timestamp=i//2,
                                    metadata={}
                                ))
                                break
        
        # If we still couldn't parse segments, create a simple structure
        if not transformed_segments:
            # Just use the original segments with the transformed text split evenly
            lines = [line for line in transformed_text.strip().split('\n') if line.strip()]
            text_per_segment = len(lines) // len(original_segments)
            
            for i, segment in enumerate(original_segments):
                start_idx = i * text_per_segment
                end_idx = start_idx + text_per_segment if i < len(original_segments) - 1 else len(lines)
                
                segment_text = " ".join(lines[start_idx:end_idx])
                if segment_text:
                    transformed_segments.append(DialogueSegment(
                        speaker=segment.speaker,
                        text=segment_text,
                        timestamp=i,
                        metadata={}
                    ))
        
        return transformed_segments
    
    def _extract_regional_adaptations(self, transformed_text: str, target_language: str) -> List[str]:
        """Extract regional adaptations made during transformation
        
        This is a simplified implementation. In a real implementation, this would
        use more sophisticated NLP techniques to identify adaptations.
        
        Args:
            transformed_text: Transformed text from Claude
            target_language: Target language
            
        Returns:
            List of regional adaptations
        """
        # This is a placeholder implementation
        # In a real implementation, this would analyze the transformed text to identify adaptations
        
        adaptations = []
        
        # Look for regional examples from the configuration
        if target_language in ConstellationConfig.REGIONAL_EXAMPLES:
            examples = ConstellationConfig.REGIONAL_EXAMPLES[target_language]
            for concept, example in examples.items():
                # Check if the example or a variation appears in the transformed text
                if concept.lower() in transformed_text.lower() or example.lower() in transformed_text.lower():
                    adaptations.append(f"Adapted {concept} using regional context")
        
        # Add a generic adaptation note
        adaptations.append(f"Content culturally adapted for {target_language} speakers")
        
        return adaptations
    
    def localize_podcast_title(self, language: Language) -> str:
        """Get the localized podcast title for a language
        
        Args:
            language: Language
            
        Returns:
            Localized podcast title
        """
        return ConstellationConfig.PODCAST_TITLES.get(language.value, "AI Builders")
    
    def get_language_intro(self, language: Language) -> str:
        """Get the standard intro for a language
        
        Args:
            language: Language
            
        Returns:
            Standard intro text
        """
        return ConstellationConfig.STANDARD_INTROS.get(language.value, "")
    
    def get_language_outro(self, language: Language) -> str:
        """Get the standard outro for a language
        
        Args:
            language: Language
            
        Returns:
            Standard outro text
        """
        return ConstellationConfig.STANDARD_OUTROS.get(language.value, "")
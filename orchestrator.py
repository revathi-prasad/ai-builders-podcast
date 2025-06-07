"""
Main orchestrator for the AI Builders Podcast System

This module provides the main orchestrator that coordinates all components
of the podcast system to generate episodes.
"""

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from config import ConstellationConfig, Language, EpisodeType
from models import EpisodeContext, DialogueSegment, ResearchResult, TransformationResult, EpisodeResult
from cache import IntelligentCache
from personality_engine import CulturalPersonalityEngine
from audio_pipeline import AudioProductionPipeline
from research_engine import ResearchEngine
from transformation import TransformationEngine

class ConstellationOrchestrator:
    """Main orchestrator for the AI Builders Podcast System
    
    This class coordinates all components of the podcast system to generate episodes.
    
    Attributes:
        cache: Instance of IntelligentCache
        personality_engine: Instance of CulturalPersonalityEngine
        audio_pipeline: Instance of AudioProductionPipeline
        research_engine: Instance of ResearchEngine
        transformation_engine: Instance of TransformationEngine
        cost_tracker: Dictionary tracking costs
    """
    
    def __init__(self):
        """Initialize the orchestrator"""
        self.cache = IntelligentCache()
        self.personality_engine = CulturalPersonalityEngine(self.cache)
        self.audio_pipeline = AudioProductionPipeline(self.cache)
        self.research_engine = ResearchEngine(self.cache)
        self.transformation_engine = TransformationEngine(self.cache)
        self.cost_tracker = {"claude": 0.0, "elevenlabs": 0.0, "total": 0.0}
    
    def generate_episode(self, context: EpisodeContext) -> EpisodeResult:
        """Generate complete episode with the Constellation System
        
        Args:
            context: EpisodeContext object containing episode configuration
            
        Returns:
            EpisodeResult object containing generated episode data
        """
        
        logging.info(f"Generating {context.episode_type.value} episode: {context.topic}")
        logging.info(f"Primary language: {context.primary_language.value}")
        logging.info(f"Cost tier: {context.cost_tier}")
        logging.info(f"Transcript only: {context.transcript_only}")
        logging.info(f"Episode number: {context.episode_number}")
        
        # Use pre-defined transcript if provided
        if context.use_transcript:
            return self._generate_from_transcript(context)
        
        # Generate the appropriate episode type
        if context.episode_type == EpisodeType.INTRODUCTION:
            return self._generate_introduction_episode(context)
        elif context.episode_type == EpisodeType.BUILD:
            return self._generate_build_episode(context)
        elif context.episode_type == EpisodeType.CONVERSATION:
            return self._generate_conversation_episode(context)
        elif context.episode_type == EpisodeType.SUMMARY:
            return self._generate_summary_episode(context)
        else:
            raise NotImplementedError(f"Episode type {context.episode_type} not yet implemented")
    
    def _generate_from_transcript(self, context: EpisodeContext) -> EpisodeResult:
        """Generate episode using a pre-defined transcript file
        Args:
            context: EpisodeContext object
        Returns:
            EpisodeResult object
        """
        try:
            # Read the transcript file
            with open(context.use_transcript, "r", encoding="utf-8") as f:
                transcript_text = f.read()
            
            # Parse the transcript into dialogue
            dialogue = self._parse_transcript(transcript_text)
            
            # Format transcript and save to cache
            formatted_transcript = self._format_transcript(dialogue)
            episode_id = f"ep{context.episode_number:02d}_{context.primary_language.value}"
            
            self.cache.save_episode_transcript(
                episode_id=episode_id,
                language=context.primary_language.value,
                episode_type=context.episode_type.value,
                topic=context.topic,
                transcript=formatted_transcript
            )
            
            # Generate transformations for secondary languages
            transformations = []
            for secondary_language in context.secondary_languages:
                logging.info(f"Transforming to {secondary_language.value}...")
                transformation = self.transformation_engine.transform_content(
                    original_segments=dialogue,
                    source_language=context.primary_language,
                    target_language=secondary_language,
                    topic=context.topic,
                    cost_tier=context.cost_tier,
                    reference_material=context.reference_material,
                    preserve_standard_sections=context.preserve_standard_sections  # Add this parameter
                )
                transformations.append(transformation)
                
                # Save the transformed transcript
                secondary_transcript = self._format_transcript(transformation.transformed_content)
                secondary_episode_id = f"ep{context.episode_number:02d}_{secondary_language.value}"
                
                self.cache.save_episode_transcript(
                    episode_id=secondary_episode_id,
                    language=secondary_language.value,
                    episode_type=context.episode_type.value,
                    topic=context.topic,
                    transcript=secondary_transcript
                )
                
                # Save to file directly
                output_file = f"outputs/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{secondary_language.value}.txt"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(secondary_transcript)
                
                logging.info(f"Secondary language transcript saved to: {output_file}")
            
            # Process audio only if not in transcript-only mode
            audio_files = []
            final_audio = None
            if not context.transcript_only:
                # Queue audio generation for each dialogue segment
                language = context.primary_language.value
                for item in dialogue:
                    if item.speaker != "MUSIC":
                        # Get voice configuration for the speaker
                        speaker = item.speaker.lower()
                        voice_config = self.audio_pipeline.get_voice_config(language, speaker)
                        # Queue the audio generation with sequence number to maintain order
                        self.audio_pipeline.queue_audio_generation(
                            item.text, 
                            voice_config, 
                            sequence=item.timestamp  # Use timestamp as sequence
                        )
                
                # Process all audio
                audio_files = self.audio_pipeline.process_audio_batch()
                
                # Merge audio files with intro/outro music
                output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
                final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
            
            # Validate the episode structure
            validation = self._validate_episode_structure(dialogue, context.primary_language.value, context.episode_type.value)
            if not validation["valid"]:
                for warning in validation["warnings"]:
                    logging.warning(f"Episode validation warning: {warning}")
            
            return EpisodeResult(
                dialogue=dialogue,
                audio_file=final_audio,
                transcript=formatted_transcript,
                transformations=transformations,  # Now includes the transformations
                metadata={
                    "episode_type": context.episode_type.value,
                    "language": context.primary_language.value,
                    "topic": context.topic,
                    "episode_number": context.episode_number,
                    "duration_estimate": validation["stats"]["estimated_duration_minutes"] * 60,  # in seconds
                    "validation": validation,
                    "cost_breakdown": self.cost_tracker.copy()
                }
            )
        
        except Exception as e:
            logging.error(f"Error generating from transcript: {e}")
            raise
    
    def _parse_transcript(self, transcript_text: str) -> List[DialogueSegment]:
        """Parse transcript text into structured dialogue
        
        Args:
            transcript_text: Raw transcript text
            
        Returns:
            List of DialogueSegment objects
        """
        lines = transcript_text.split('\n')
        dialogue = []
        timestamp = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line == "[INTRO MUSIC]" or line == "[OUTRO MUSIC]":
                dialogue.append(DialogueSegment(
                    speaker="MUSIC",
                    text=line,
                    timestamp=timestamp
                ))
                timestamp += 1
            elif ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    speaker, text = parts
                    dialogue.append(DialogueSegment(
                        speaker=speaker.strip(),
                        text=text.strip(),
                        timestamp=timestamp
                    ))
                    timestamp += 1
        
        return dialogue
    
    def generate_episode_with_documents(self, context: EpisodeContext, document_paths: List[str]) -> EpisodeResult:
        """Generate episode with custom documents for research
        
        Args:
            context: EpisodeContext object
            document_paths: List of paths to custom documents
            
        Returns:
            EpisodeResult object
        """
        # Process the documents first
        research_result = self.research_engine.research_topic(
            context.topic,
            depth="deep",
            regions=["global", "india"],
            language=context.primary_language.value,
            documents=document_paths
        )
        
        # Now generate the episode
        if context.episode_type == EpisodeType.INTRODUCTION:
            return self._generate_introduction_episode(context, custom_research=research_result)
        elif context.episode_type == EpisodeType.BUILD:
            return self._generate_build_episode(context, custom_research=research_result)
        elif context.episode_type == EpisodeType.CONVERSATION:
            return self._generate_conversation_episode(context, custom_research=research_result)
        elif context.episode_type == EpisodeType.SUMMARY:
            return self._generate_summary_episode(context)
        else:
            raise NotImplementedError(f"Episode type {context.episode_type} not yet implemented")
    
    def _generate_introduction_episode(self, context: EpisodeContext, custom_research: Optional[ResearchResult] = None) -> EpisodeResult:
        """Generate introduction episode
        
        Args:
            context: EpisodeContext object
            
        Returns:
            EpisodeResult object
        """
        
        # Get the appropriate hosts for this language
        language = context.primary_language.value
        hosts = list(ConstellationConfig.VOICE_LIBRARY[language].keys())
        host1, host2 = hosts[0].lower(), hosts[1].lower()
        
        # Get the podcast title for this language
        podcast_title = self.transformation_engine.localize_podcast_title(context.primary_language)
        
        # Research the topic if needed (unless custom research is provided)
        research_data = None
        research_result = None
        
        if custom_research:
            research_result = custom_research
            research_data = {
                "summary": research_result.summary,
                "key_points": research_result.key_points,
                "examples": research_result.examples,
                "regional_insights": research_result.regional_insights
            }
        elif context.episode_type != EpisodeType.INTRODUCTION or context.episode_number > 0:
            research_result = self.research_engine.research_topic(
                context.topic,
                depth="standard",
                regions=["global", "india"],
                language=language
            )
            research_data = {
                "summary": research_result.summary,
                "key_points": research_result.key_points,
                "examples": research_result.examples,
                "regional_insights": research_result.regional_insights
            }
        
        # Create full dialogue (intro, content, outro)
        dialogue = []
        
        # Add standard intro if requested
        if context.include_intro:
            intro_text = ConstellationConfig.STANDARD_INTROS[language]
            intro_parts = intro_text.split("\n\n")
            
            for part in intro_parts:
                if part.startswith("[INTRO MUSIC]"):
                    dialogue.append(DialogueSegment(
                        speaker="MUSIC",
                        text="[INTRO MUSIC]",
                        timestamp=len(dialogue)
                    ))
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append(DialogueSegment(
                        speaker=speaker,
                        text=text.strip(),
                        timestamp=len(dialogue)
                    ))
        
        # Generate main episode content with episode number awareness
        episode_segments = self.personality_engine.generate_episode_segments(
            host1=host1,
            host2=host2,
            language=context.primary_language,
            episode_type=context.episode_type,
            topic=context.topic,
            podcast_title=podcast_title,
            episode_number=context.episode_number,  # Pass episode number for appropriate templating
            cost_tier=context.cost_tier,
            research_data=research_data,
            reference_material=context.reference_material
        )
        
        # Add episode segments to dialogue
        dialogue.extend(episode_segments)
        
        # Add standard outro if requested
        if context.include_outro:
            outro_text = ConstellationConfig.STANDARD_OUTROS[language]
            outro_parts = outro_text.split("\n\n")
            
            for part in outro_parts:
                if part.startswith("[OUTRO MUSIC]"):
                    dialogue.append(DialogueSegment(
                        speaker="MUSIC",
                        text="[OUTRO MUSIC]",
                        timestamp=len(dialogue)
                    ))
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append(DialogueSegment(
                        speaker=speaker,
                        text=text.strip(),
                        timestamp=len(dialogue)
                    ))
        
        # Format transcript and save to cache
        transcript = self._format_transcript(dialogue)
        episode_id = f"ep{context.episode_number:02d}_{context.primary_language.value}"
        
        self.cache.save_episode_transcript(
            episode_id=episode_id,
            language=language,
            episode_type=context.episode_type.value,
            topic=context.topic,
            transcript=transcript
        )
        
        # Generate transformations for secondary languages
        transformations = []
        for secondary_language in context.secondary_languages:
            transformation = self.transformation_engine.transform_content(
                original_segments=dialogue,
                source_language=context.primary_language,
                target_language=secondary_language,
                topic=context.topic,
                cost_tier=context.cost_tier,
                reference_material=context.reference_material,
                preserve_standard_sections=context.preserve_standard_sections
            )
            transformations.append(transformation)
            
            # Save the transformed transcript
            secondary_transcript = self._format_transcript(transformation.transformed_content)
            secondary_episode_id = f"ep{context.episode_number:02d}_{secondary_language.value}"
            
            self.cache.save_episode_transcript(
                episode_id=secondary_episode_id,
                language=secondary_language.value,
                episode_type=context.episode_type.value,
                topic=context.topic,
                transcript=secondary_transcript
            )
        
        # Process audio only if not in transcript-only mode
        audio_files = []
        final_audio = None
        if not context.transcript_only:
            # Queue standard intro if appropriate
            if context.include_intro:
                self.audio_pipeline.queue_standard_intro(language, podcast_title)
            
            # Queue audio generation for each dialogue segment
            for item in dialogue:
                if item.speaker != "MUSIC":
                    # Get voice configuration for the speaker
                    speaker = item.speaker.lower()
                    voice_config = self.audio_pipeline.get_voice_config(language, speaker)
                    # Queue the audio generation with sequence number to maintain order
                    self.audio_pipeline.queue_audio_generation(
                        item.text, 
                        voice_config, 
                        sequence=item.timestamp
                    )
            
            # Queue standard outro if appropriate
            if context.include_outro:
                self.audio_pipeline.queue_standard_outro(language, podcast_title)
            
            # Process all audio
            audio_files = self.audio_pipeline.process_audio_batch()
            
            # Merge audio files with intro/outro music
            output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
            final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
        
        # Validate the episode structure
        validation = self._validate_episode_structure(dialogue, language, context.episode_type.value)
        if not validation["valid"]:
            for warning in validation["warnings"]:
                logging.warning(f"Episode validation warning: {warning}")
        
        # Create GitHub resources for research citations if available
        github_resources = None
        if research_data:
            github_resources = self.research_engine.create_github_resources(
                research_result,
                language,
                context.episode_number
            )
        
        return EpisodeResult(
            dialogue=dialogue,
            audio_file=final_audio,
            transcript=transcript,
            research=research_result if research_data else None,
            transformations=transformations,
            metadata={
                "episode_type": context.episode_type.value,
                "language": context.primary_language.value,
                "topic": context.topic,
                "episode_number": context.episode_number,
                "podcast_title": podcast_title,
                "duration_estimate": validation["stats"]["estimated_duration_minutes"] * 60,  # in seconds
                "validation": validation,
                "cost_breakdown": self.cost_tracker.copy(),
                "github_resources": github_resources
            }
        )
    
    def _generate_build_episode(self, context: EpisodeContext, custom_research: Optional[ResearchResult] = None) -> EpisodeResult:
        """Generate build episode
        
        Args:
            context: EpisodeContext object
            
        Returns:
            EpisodeResult object
        """
        
        # Get the appropriate hosts for this language
        language = context.primary_language.value
        hosts = list(ConstellationConfig.VOICE_LIBRARY[language].keys())
        host1, host2 = hosts[0].lower(), hosts[1].lower()
        
        # Get the podcast title for this language
        podcast_title = self.transformation_engine.localize_podcast_title(context.primary_language)
        
        # Research the topic
        if custom_research:
            research_result = custom_research
        else:
            research_result = self.research_engine.research_topic(
                context.topic,
                depth="deep",
                regions=["global", "india"],
                language=language
            )
        
        research_data = {
            "summary": research_result.summary,
            "key_points": research_result.key_points,
            "examples": research_result.examples,
            "regional_insights": research_result.regional_insights
        }
        
        # Create full dialogue (intro, content, outro)
        dialogue = []
        
        # Add standard intro if requested
        if context.include_intro:
            intro_text = ConstellationConfig.STANDARD_INTROS[language]
            intro_parts = intro_text.split("\n\n")
            
            for part in intro_parts:
                if part.startswith("[INTRO MUSIC]"):
                    dialogue.append(DialogueSegment(
                        speaker="MUSIC",
                        text="[INTRO MUSIC]",
                        timestamp=len(dialogue)
                    ))
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append(DialogueSegment(
                        speaker=speaker,
                        text=text.strip(),
                        timestamp=len(dialogue)
                    ))
        
        # Generate main episode content with episode number awareness
        episode_segments = self.personality_engine.generate_episode_segments(
            host1=host1,
            host2=host2,
            language=context.primary_language,
            episode_type=context.episode_type,
            topic=context.topic,
            podcast_title=podcast_title,
            episode_number=context.episode_number,
            cost_tier=context.cost_tier,
            research_data=research_data,
            reference_material=context.reference_material
        )
        
        # Add episode segments to dialogue
        dialogue.extend(episode_segments)
        
        # Add standard outro if requested
        if context.include_outro:
            outro_text = ConstellationConfig.STANDARD_OUTROS[language]
            outro_parts = outro_text.split("\n\n")
            
            for part in outro_parts:
                if part.startswith("[OUTRO MUSIC]"):
                    dialogue.append(DialogueSegment(
                        speaker="MUSIC",
                        text="[OUTRO MUSIC]",
                        timestamp=len(dialogue)
                    ))
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append(DialogueSegment(
                        speaker=speaker,
                        text=text.strip(),
                        timestamp=len(dialogue)
                    ))
        
        # Format transcript and save to cache
        transcript = self._format_transcript(dialogue)
        episode_id = f"ep{context.episode_number:02d}_{context.primary_language.value}"
        
        self.cache.save_episode_transcript(
            episode_id=episode_id,
            language=language,
            episode_type=context.episode_type.value,
            topic=context.topic,
            transcript=transcript
        )
        
        # Generate transformations for secondary languages
        transformations = []
        for secondary_language in context.secondary_languages:
            transformation = self.transformation_engine.transform_content(
                original_segments=dialogue,
                source_language=context.primary_language,
                target_language=secondary_language,
                topic=context.topic,
                cost_tier=context.cost_tier,
                reference_material=context.reference_material,
                preserve_standard_sections=context.preserve_standard_sections
            )
            transformations.append(transformation)
            
            # Save the transformed transcript
            secondary_transcript = self._format_transcript(transformation.transformed_content)
            secondary_episode_id = f"ep{context.episode_number:02d}_{secondary_language.value}"
            
            self.cache.save_episode_transcript(
                episode_id=secondary_episode_id,
                language=secondary_language.value,
                episode_type=context.episode_type.value,
                topic=context.topic,
                transcript=secondary_transcript
            )
        
        # Process audio only if not in transcript-only mode
        audio_files = []
        final_audio = None
        if not context.transcript_only:
            # Queue standard intro if appropriate
            if context.include_intro:
                self.audio_pipeline.queue_standard_intro(language, podcast_title)
            
            # Queue audio generation for each dialogue segment
            for item in dialogue:
                if item.speaker != "MUSIC":
                    # Get voice configuration for the speaker
                    speaker = item.speaker.lower()
                    voice_config = self.audio_pipeline.get_voice_config(language, speaker)
                    # Queue the audio generation with sequence number to maintain order
                    self.audio_pipeline.queue_audio_generation(
                        item.text, 
                        voice_config, 
                        sequence=item.timestamp
                    )
            
            # Queue standard outro if appropriate
            if context.include_outro:
                self.audio_pipeline.queue_standard_outro(language, podcast_title)
            
            # Process all audio
            audio_files = self.audio_pipeline.process_audio_batch()
            
            # Merge audio files with intro/outro music
            output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
            final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
        
        # Validate the episode structure
        validation = self._validate_episode_structure(dialogue, language, context.episode_type.value)
        if not validation["valid"]:
            for warning in validation["warnings"]:
                logging.warning(f"Episode validation warning: {warning}")
        
        # Create GitHub resources for research citations
        github_resources = self.research_engine.create_github_resources(
            research_result,
            language,
            context.episode_number
        )
        
        return EpisodeResult(
            dialogue=dialogue,
            audio_file=final_audio,
            transcript=transcript,
            research=research_result,
            transformations=transformations,
            metadata={
                "episode_type": context.episode_type.value,
                "language": context.primary_language.value,
                "topic": context.topic,
                "episode_number": context.episode_number,
                "podcast_title": podcast_title,
                "duration_estimate": validation["stats"]["estimated_duration_minutes"] * 60,  # in seconds
                "validation": validation,
                "cost_breakdown": self.cost_tracker.copy(),
                "github_resources": github_resources
            }
        )
    
    def _generate_conversation_episode(self, context: EpisodeContext, custom_research: Optional[ResearchResult] = None) -> EpisodeResult:
        """Generate conversation episode
        
        Args:
            context: EpisodeContext object
            
        Returns:
            EpisodeResult object
        """
        
        # Get the appropriate hosts for this language
        language = context.primary_language.value
        hosts = list(ConstellationConfig.VOICE_LIBRARY[language].keys())
        host1, host2 = hosts[0].lower(), hosts[1].lower()
        
        # Get the podcast title for this language
        podcast_title = self.transformation_engine.localize_podcast_title(context.primary_language)
        
        # Research the topic
        if custom_research:
            research_result = custom_research
        else:
            research_result = self.research_engine.research_topic(
                context.topic,
                depth="standard",
                regions=["global", "india"],
                language=language
            )
        
        research_data = {
            "summary": research_result.summary,
            "key_points": research_result.key_points,
            "examples": research_result.examples,
            "regional_insights": research_result.regional_insights
        }
        
        # Create full dialogue (intro, content, outro)
        dialogue = []
        
        # Add standard intro if requested
        if context.include_intro:
            intro_text = ConstellationConfig.STANDARD_INTROS[language]
            intro_parts = intro_text.split("\n\n")
            
            for part in intro_parts:
                if part.startswith("[INTRO MUSIC]"):
                    dialogue.append(DialogueSegment(
                        speaker="MUSIC",
                        text="[INTRO MUSIC]",
                        timestamp=len(dialogue)
                    ))
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append(DialogueSegment(
                        speaker=speaker,
                        text=text.strip(),
                        timestamp=len(dialogue)
                    ))
        
        # Generate main episode content with episode number awareness
        episode_segments = self.personality_engine.generate_episode_segments(
            host1=host1,
            host2=host2,
            language=context.primary_language,
            episode_type=context.episode_type,
            topic=context.topic,
            podcast_title=podcast_title,
            episode_number=context.episode_number,
            cost_tier=context.cost_tier,
            research_data=research_data,
            reference_material=context.reference_material
        )
        
        # Add episode segments to dialogue
        dialogue.extend(episode_segments)
        
        # Add standard outro if requested
        if context.include_outro:
            outro_text = ConstellationConfig.STANDARD_OUTROS[language]
            outro_parts = outro_text.split("\n\n")
            
            for part in outro_parts:
                if part.startswith("[OUTRO MUSIC]"):
                    dialogue.append(DialogueSegment(
                        speaker="MUSIC",
                        text="[OUTRO MUSIC]",
                        timestamp=len(dialogue)
                    ))
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append(DialogueSegment(
                        speaker=speaker,
                        text=text.strip(),
                        timestamp=len(dialogue)
                    ))
        
        # Format transcript and save to cache
        transcript = self._format_transcript(dialogue)
        episode_id = f"ep{context.episode_number:02d}_{context.primary_language.value}"
        
        self.cache.save_episode_transcript(
            episode_id=episode_id,
            language=language,
            episode_type=context.episode_type.value,
            topic=context.topic,
            transcript=transcript
        )
        
        # Generate transformations for secondary languages
        transformations = []
        for secondary_language in context.secondary_languages:
            transformation = self.transformation_engine.transform_content(
                original_segments=dialogue,
                source_language=context.primary_language,
                target_language=secondary_language,
                topic=context.topic,
                cost_tier=context.cost_tier,
                reference_material=context.reference_material,
                preserve_standard_sections=context.preserve_standard_sections
            )
            transformations.append(transformation)
            
            # Save the transformed transcript
            secondary_transcript = self._format_transcript(transformation.transformed_content)
            secondary_episode_id = f"ep{context.episode_number:02d}_{secondary_language.value}"
            
            self.cache.save_episode_transcript(
                episode_id=secondary_episode_id,
                language=secondary_language.value,
                episode_type=context.episode_type.value,
                topic=context.topic,
                transcript=secondary_transcript
            )
        
        # Process audio only if not in transcript-only mode
        audio_files = []
        final_audio = None
        if not context.transcript_only:
            # Queue standard intro if appropriate
            if context.include_intro:
                self.audio_pipeline.queue_standard_intro(language, podcast_title)
            
            # Queue audio generation for each dialogue segment
            for item in dialogue:
                if item.speaker != "MUSIC":
                    # Get voice configuration for the speaker
                    speaker = item.speaker.lower()
                    voice_config = self.audio_pipeline.get_voice_config(language, speaker)
                    # Queue the audio generation with sequence number to maintain order
                    self.audio_pipeline.queue_audio_generation(
                        item.text, 
                        voice_config, 
                        sequence=item.timestamp
                    )
            
            # Queue standard outro if appropriate
            if context.include_outro:
                self.audio_pipeline.queue_standard_outro(language, podcast_title)
            
            # Process all audio
            audio_files = self.audio_pipeline.process_audio_batch()
            
            # Merge audio files with intro/outro music
            output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
            final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
        
        # Validate the episode structure
        validation = self._validate_episode_structure(dialogue, language, context.episode_type.value)
        if not validation["valid"]:
            for warning in validation["warnings"]:
                logging.warning(f"Episode validation warning: {warning}")
        
        # Create GitHub resources for research citations
        github_resources = self.research_engine.create_github_resources(
            research_result,
            language,
            context.episode_number
        )
        
        return EpisodeResult(
            dialogue=dialogue,
            audio_file=final_audio,
            transcript=transcript,
            research=research_result,
            transformations=transformations,
            metadata={
                "episode_type": context.episode_type.value,
                "language": context.primary_language.value,
                "topic": context.topic,
                "episode_number": context.episode_number,
                "podcast_title": podcast_title,
                "duration_estimate": validation["stats"]["estimated_duration_minutes"] * 60,  # in seconds
                "validation": validation,
                "cost_breakdown": self.cost_tracker.copy(),
                "github_resources": github_resources
            }
        )
    
    def _generate_summary_episode(self, context: EpisodeContext) -> EpisodeResult:
        """Generate summary episode for secondary languages
        
        Args:
            context: EpisodeContext object
            
        Returns:
            EpisodeResult object
        """
        # This would extract key insights and create shorter versions
        # for secondary languages - simplified implementation
        
        # Find the original episode in the primary language
        original_episode_id = f"ep{context.episode_number:02d}_{context.primary_language.value}"
        original_transcript_data = self.cache.get_episode_transcript(original_episode_id)
        
        if not original_transcript_data:
            raise ValueError(f"Original episode transcript not found: {original_episode_id}")
        
        # Parse the original transcript into dialogue segments
        original_transcript = original_transcript_data["transcript"]
        original_dialogue = self._parse_transcript(original_transcript)
        
        # Get the podcast title for the target language
        podcast_title = self.transformation_engine.localize_podcast_title(context.primary_language)
        
        # Transform the content to the target language
        transformation = self.transformation_engine.transform_content(
            original_segments=original_dialogue,
            source_language=context.primary_language,
            target_language=context.primary_language,  # Same language, but summarized
            topic=context.topic,
            cost_tier=context.cost_tier,
            reference_material=f"This should be a summary episode extracting key insights from the original episode about '{context.topic}'. Focus on the most important points and make it about 1/3 the length of the original.",
            preserve_standard_sections=context.preserve_standard_sections
        )
        
        dialogue = transformation.transformed_content
        
        # Format transcript and save to cache
        transcript = self._format_transcript(dialogue)
        episode_id = f"ep{context.episode_number:02d}_summary_{context.primary_language.value}"
        
        self.cache.save_episode_transcript(
            episode_id=episode_id,
            language=context.primary_language.value,
            episode_type="summary",
            topic=context.topic,
            transcript=transcript
        )
        
        # Process audio only if not in transcript-only mode
        audio_files = []
        final_audio = None
        if not context.transcript_only:
            # Queue standard intro
            self.audio_pipeline.queue_standard_intro(context.primary_language.value, podcast_title)
            
            # Queue audio generation for each dialogue segment
            for item in dialogue:
                if item.speaker != "MUSIC":
                    # Get voice configuration for the speaker
                    speaker = item.speaker.lower()
                    voice_config = self.audio_pipeline.get_voice_config(context.primary_language.value, speaker)
                    # Queue the audio generation with sequence number to maintain order
                    self.audio_pipeline.queue_audio_generation(
                        item.text, 
                        voice_config, 
                        sequence=item.timestamp
                    )
            
            # Queue standard outro
            self.audio_pipeline.queue_standard_outro(context.primary_language.value, podcast_title)
            
            # Process all audio
            audio_files = self.audio_pipeline.process_audio_batch()
            
            # Merge audio files with intro/outro music
            output_file = f"episodes/ep{context.episode_number:02d}_summary_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
            final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, context.primary_language.value)
        
        return EpisodeResult(
            dialogue=dialogue,
            audio_file=final_audio,
            transcript=transcript,
            metadata={
                "episode_type": "summary",
                "language": context.primary_language.value,
                "topic": context.topic,
                "episode_number": context.episode_number,
                "podcast_title": podcast_title,
                "original_episode_id": original_episode_id,
                "cost_breakdown": self.cost_tracker.copy()
            }
        )
    
    def _validate_episode_structure(self, dialogue: List[DialogueSegment], language: str, episode_type: str) -> Dict:
        """Validate episode structure and provide warnings if issues are detected
        
        Args:
            dialogue: List of dialogue segments
            language: Language code
            episode_type: Episode type
            
        Returns:
            Dictionary containing validation results
        """
        validation = {"valid": True, "warnings": []}
        
        # Check episode length
        spoken_segments = [s for s in dialogue if s.speaker != "MUSIC"]
        if len(spoken_segments) < 8:
            validation["warnings"].append(f"Episode may be too short: only {len(spoken_segments)} spoken segments")
            validation["valid"] = False
        
        # Check for duplicate introductions
        host_intros = {}
        for segment in dialogue[:6]:  # Check first 6 segments
            if segment.speaker != "MUSIC":
                speaker = segment.speaker
                text = segment.text.lower()
                if "i'm" in text and speaker.lower() in text.lower():
                    if speaker in host_intros:
                        validation["warnings"].append(f"Potential duplicate introduction for {speaker}")
                    host_intros[speaker] = True
        
        # Check for AI disclosure
        ai_terms = ["ai host", "language model", "chatgpt", "claude", "llm"]
        has_disclosure = False
        for segment in dialogue[:4]:  # Check first 4 segments
            if segment.speaker != "MUSIC":
                if any(term in segment.text.lower() for term in ai_terms):
                    has_disclosure = True
                    break
        
        if not has_disclosure:
            validation["warnings"].append("Missing AI host disclosure in introduction")
        
        # Add word count statistics
        total_words = sum(len(segment.text.split()) for segment in spoken_segments)
        avg_words = total_words / max(1, len(spoken_segments))
        validation["stats"] = {
            "total_segments": len(dialogue),
            "spoken_segments": len(spoken_segments),
            "total_words": total_words,
            "avg_words_per_segment": avg_words,
            "estimated_duration_minutes": total_words / 150  # Assuming 150 words per minute
        }
        
        return validation
    
    def _format_transcript(self, dialogue: List[DialogueSegment]) -> str:
        """Format dialogue as readable transcript
        
        Args:
            dialogue: List of dialogue segments
            
        Returns:
            Formatted transcript text
        """
        transcript = []
        for entry in dialogue:
            if entry.speaker == "MUSIC":
                transcript.append(entry.text)
            else:
                transcript.append(f"{entry.speaker}: {entry.text}")
        
        return "\n\n".join(transcript)

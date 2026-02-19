"""
Audio production pipeline for the AI Builders Podcast System

This module handles audio generation, processing, and merging for podcast episodes.
"""

import hashlib
import os
import time
import logging
from typing import Dict, List, Optional, Any, Tuple

import requests
from pydub import AudioSegment, effects

from config import ConstellationConfig
from cache import IntelligentCache

class AudioProductionPipeline:
    """Handles audio generation with cost optimization
    
    This class provides an audio production pipeline for generating, processing,
    and merging audio for podcast episodes.
    
    Attributes:
        cache: Instance of IntelligentCache for caching audio files
    """
    
    def __init__(self, cache: IntelligentCache):
        """Initialize the audio production pipeline
        
        Args:
            cache: Instance of IntelligentCache for caching audio files
        """
        self.cache = cache
        self.audio_queue = []
    
    def queue_audio_generation(self, text: str, voice_config: Dict, priority: str = "standard", sequence: int = 0):
        """Queue audio for batch processing
        
        Args:
            text: Text to convert to speech
            voice_config: Voice configuration
            priority: Priority level ("low", "standard", "high")
            sequence: Sequence number for maintaining order
        """
        self.audio_queue.append({
            "text": text,
            "voice_config": voice_config,
            "priority": priority,
            "timestamp": time.time(),
            "sequence": sequence  # Add sequence number to maintain conversation order
        })

    def process_audio_batch(self) -> List[str]:
        """Process all queued audio efficiently
        
        Returns:
            List of paths to generated audio files
        """
        if not self.audio_queue:
            return []
        
        logging.info(f"Processing batch of {len(self.audio_queue)} audio items...")
        
        # First sort by voice ID for API efficiency, but keep track of original sequence
        self.audio_queue.sort(key=lambda x: (x["voice_config"]["voice_id"], x.get("sequence", 0)))
        
        generated_files_with_sequence = []
        total_cost = 0.0
        
        for item in self.audio_queue:
            # Special handling for pre-recorded audio (like intros/outros)
            if item.get("prerecorded", False):
                if "prerecorded_path" in item["voice_config"]:
                    generated_files_with_sequence.append({
                        "file": item["voice_config"]["prerecorded_path"],
                        "sequence": item.get("sequence", 0)
                    })
                    logging.info(f"Using pre-recorded audio: {item['voice_config']['prerecorded_path']}")
                continue
                
            # Check cache first
            cache_key = hashlib.md5(
                f"{item['text']}_{item['voice_config']['voice_id']}".encode()
            ).hexdigest()
            
            cached_file = self.cache.get_cached_audio_file(item["text"], item["voice_config"]["voice_id"])
            if cached_file and os.path.exists(cached_file):
                generated_files_with_sequence.append({
                    "file": cached_file,
                    "sequence": item.get("sequence", 0)
                })
                logging.info("Audio cache hit - saved ~$1.50")
                continue
            
            # Generate new audio
            audio_file = self._generate_audio(item["text"], item["voice_config"])
            if audio_file:
                generated_files_with_sequence.append({
                    "file": audio_file,
                    "sequence": item.get("sequence", 0)
                })
                cost = len(item["text"]) * 0.00022
                total_cost += cost
                
                # Cache the audio file
                self.cache.cache_audio_file(
                    item["text"], 
                    item["voice_config"]["voice_id"], 
                    audio_file, 
                    len(item["text"]), 
                    cost
                )
        
        logging.info(f"Audio batch processed - cost: ${total_cost:.2f}")
        self.audio_queue.clear()
        
        # Sort files back into original sequence order before returning
        generated_files_with_sequence.sort(key=lambda x: x["sequence"])
        return [item["file"] for item in generated_files_with_sequence]
    
    def _generate_audio(self, text: str, voice_config: Dict) -> Optional[str]:
        """Generate audio using ElevenLabs
        
        Args:
            text: Text to convert to speech
            voice_config: Voice configuration
            
        Returns:
            Path to generated audio file, or None if generation failed
        """
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_config['voice_id']}"
        
        # Add some light markdown emphasis for better intonation
        enhanced_text = self._add_emphasis_markers(text)
        
        data = {
            "text": enhanced_text,
            "model_id": voice_config.get("model", ConstellationConfig.ELEVENLABS_MODELS["standard"]),
            "voice_settings": voice_config.get("settings", {
                "stability": 0.35,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            })
        }
        
        headers = {
            "Accept": "audio/mpeg",
            "xi-api-key": ConstellationConfig.ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                timestamp = int(time.time())
                filename = f"audio-files/{timestamp}_{voice_config['voice_id'][:8]}.mp3"
                
                os.makedirs("audio-files", exist_ok=True)
                with open(filename, "wb") as f:
                    f.write(response.content)
                
                return filename
            else:
                logging.error(f"ElevenLabs API error: {response.text}")
                return None
                
        except Exception as e:
            logging.error(f"Audio generation error: {e}")
            return None
    
    def _add_emphasis_markers(self, text: str) -> str:
        """Add light emphasis markers to improve ElevenLabs intonation
        
        Args:
            text: Text to enhance
            
        Returns:
            Text with emphasis markers added
        """
        # Define words/phrases to emphasize
        emphasis_words = [
            "really", "very", "absolutely", "definitely", "extremely",
            "important", "critical", "essential", "crucial", "vital",
            "never", "always", "must", "need to", "have to",
            "amazing", "incredible", "fantastic", "awesome", "wonderful",
            "terrible", "horrible", "awful", "disastrous"
        ]
        
        # Simple rule-based emphasis marking
        words = text.split()
        for i, word in enumerate(words):
            # Strip punctuation for comparison
            clean_word = word.lower().strip(".,!?;:")
            
            # Add emphasis markers
            if clean_word in emphasis_words:
                # Add asterisks for emphasis (works in ElevenLabs)
                words[i] = word.replace(clean_word, f"*{clean_word}*")
                
        enhanced_text = " ".join(words)
        
        # Handle question marks for better intonation
        enhanced_text = enhanced_text.replace("?", "?↗")
        
        return enhanced_text
    
    def queue_standard_intro(self, language: str, podcast_title: str):
        """Queue standard intro audio
        
        Args:
            language: Language code
            podcast_title: Podcast title
        """
        # Check if using pre-recorded intros
        if ConstellationConfig.AUDIO_SETTINGS["use_prerecorded_intros"]:
            intro_file = os.path.join(
                ConstellationConfig.AUDIO_SETTINGS["prerecorded_intro_dir"],
                f"intro_{language}.mp3"
            )
            
            if os.path.exists(intro_file):
                # Add it to the audio queue with special handling
                self.audio_queue.append({
                    "text": f"[PRE_RECORDED_INTRO]",
                    "voice_config": {"voice_id": "prerecorded", "prerecorded_path": intro_file},
                    "priority": "high",
                    "timestamp": time.time(),
                    "sequence": -1000,  # Ensure it comes first
                    "prerecorded": True
                })
                
                return True
        
        # If not using pre-recorded intros or file not found,
        # queue intro music marker (will be replaced with actual music)
        self.audio_queue.append({
            "text": "[INTRO MUSIC]",
            "voice_config": {"voice_id": "music", "prerecorded_path": "music"},
            "priority": "high",
            "timestamp": time.time(),
            "sequence": -1000,  # Ensure it comes first
            "prerecorded": True
        })
        
        return True
    
    def queue_standard_outro(self, language: str, podcast_title: str):
        """Queue standard outro audio
        
        Args:
            language: Language code
            podcast_title: Podcast title
        """
        # Check if using pre-recorded outros
        if ConstellationConfig.AUDIO_SETTINGS["use_prerecorded_intros"]:
            outro_file = os.path.join(
                ConstellationConfig.AUDIO_SETTINGS["prerecorded_outro_dir"],
                f"outro_{language}.mp3"
            )
            
            if os.path.exists(outro_file):
                # Add it to the audio queue with special handling
                self.audio_queue.append({
                    "text": f"[PRE_RECORDED_OUTRO]",
                    "voice_config": {"voice_id": "prerecorded", "prerecorded_path": outro_file},
                    "priority": "high",
                    "timestamp": time.time(),
                    "sequence": 10000,  # Ensure it comes last
                    "prerecorded": True
                })
                
                return True
        
        # If not using pre-recorded outros or file not found,
        # queue outro music marker (will be replaced with actual music)
        self.audio_queue.append({
            "text": "[OUTRO MUSIC]",
            "voice_config": {"voice_id": "music", "prerecorded_path": "music"},
            "priority": "high",
            "timestamp": time.time(),
            "sequence": 10000,  # Ensure it comes last
            "prerecorded": True
        })
        
        return True
    
    def add_intro_outro_music(self, audio_files: List[str], output_file: str, language: str) -> str:
        """Add intro and outro music to the episode with precise timing
        
        Args:
            audio_files: List of audio file paths
            output_file: Path to output file
            language: Language code
            
        Returns:
            Path to the final audio file
        """
        if not audio_files:
            return None
        
        # Load language-specific music if available, otherwise use default
        intro_paths = ConstellationConfig.AUDIO_SETTINGS["intro_music_paths"]
        outro_paths = ConstellationConfig.AUDIO_SETTINGS["outro_music_paths"]
        
        intro_path = intro_paths.get(language, intro_paths["default"])
        outro_path = outro_paths.get(language, outro_paths["default"])
        
        if not os.path.exists(intro_path):
            logging.warning(f"Intro music file for {language} not found at {intro_path}, using default")
            intro_path = intro_paths["default"]
            
        if not os.path.exists(outro_path):
            logging.warning(f"Outro music file for {language} not found at {outro_path}, using default")
            outro_path = outro_paths["default"]
            
        if not os.path.exists(intro_path) or not os.path.exists(outro_path):
            logging.warning("Intro or outro music files not found, proceeding without music")
            return self._merge_audio_files(audio_files, output_file)
        
        try:
            intro_music = AudioSegment.from_mp3(intro_path)
            outro_music = AudioSegment.from_mp3(outro_path)
            
            # Process the audio segments
            intro_segments = []
            main_segments = []
            outro_segments = []
            
            # Flag to track where we are in the episode
            in_intro = True
            in_outro = False
            
            # First pass: categorize segments and convert audio
            for i, file in enumerate(audio_files):
                segment = AudioSegment.from_mp3(file)
                if ConstellationConfig.AUDIO_SETTINGS["normalize_audio"]:
                    segment = effects.normalize(segment)
                
                # Look at filename to determine if it's music
                is_music = "MUSIC" in file or file.endswith("prerecorded")
                
                # If we find a music marker in main content, it's likely outro time
                if not in_intro and is_music:
                    in_outro = True
                
                # Categorize based on where we are
                if in_intro:
                    # If it's a music marker, it's the intro music marker
                    if is_music:
                        # Skip this - we'll use the real intro music file
                        pass
                    else:
                        # It's an intro spoken part
                        intro_segments.append(segment)
                        # After first real spoken content, we're not in intro anymore
                        in_intro = False
                elif in_outro:
                    # If it's a music marker, it's the outro music marker
                    if is_music:
                        # Skip this - we'll use the real outro music file
                        pass
                    else:
                        # It's an outro spoken part
                        outro_segments.append(segment)
                else:
                    # It's main content
                    main_segments.append(segment)
            
            # Create pause
            pause = AudioSegment.silent(duration=ConstellationConfig.AUDIO_SETTINGS["pause_between_turns"])
            
            # Start with intro music 
            combined = intro_music.fade_out(2000)  # 2-second fade out for intro music
            
            # Add intro spoken content if any
            for segment in intro_segments:
                combined += pause + segment
            
            # Add main content
            for segment in main_segments:
                combined += pause + segment
            
            # Add outro spoken content if any
            for segment in outro_segments:
                combined += pause + segment
            
            # Add outro music with fade-in
            combined += pause + outro_music.fade_in(2000)  # 2-second fade in for outro music
            
            # Export the final audio
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            combined.export(output_file, format="mp3")
            
            logging.info(f"Created podcast with intro/outro music: {output_file}")
            return output_file
            
        except Exception as e:
            logging.error(f"Error adding intro/outro music: {e}")
            # Fall back to simple merge if music addition fails
            return self._merge_audio_files(audio_files, output_file)
    
    def _merge_audio_files(self, filenames: List[str], output_file: str) -> str:
        """Merge audio files without intro/outro music
        
        Args:
            filenames: List of audio file paths
            output_file: Path to output file
            
        Returns:
            Path to the merged audio file
        """
        if not filenames:
            return None
        
        combined = AudioSegment.from_mp3(filenames[0])
        if ConstellationConfig.AUDIO_SETTINGS["normalize_audio"]:
            combined = effects.normalize(combined)
        
        pause = AudioSegment.silent(duration=ConstellationConfig.AUDIO_SETTINGS["pause_between_turns"])
        
        for file in filenames[1:]:
            segment = AudioSegment.from_mp3(file)
            if ConstellationConfig.AUDIO_SETTINGS["normalize_audio"]:
                segment = effects.normalize(segment)
            combined += pause + segment
        
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        combined.export(output_file, format="mp3")
        
        logging.info(f"Created podcast: {output_file}")
        return output_file
    
    def _merge_with_prerecorded(self, intro_file: str, outro_file: str, content_files: List[str], output_file: str) -> str:
        """Merge content with pre-recorded intro and outro files
        
        Args:
            intro_file: Path to intro file
            outro_file: Path to outro file
            content_files: List of content file paths
            output_file: Path to output file
            
        Returns:
            Path to the merged audio file
        """
        if not content_files:
            logging.warning("No content files to merge with intro/outro")
            return None
            
        try:
            # Load the pre-recorded files
            intro = AudioSegment.from_mp3(intro_file)
            outro = AudioSegment.from_mp3(outro_file)
            
            # Create pause
            pause = AudioSegment.silent(duration=ConstellationConfig.AUDIO_SETTINGS["pause_between_turns"])
            
            # Start with intro
            combined = intro
            
            # Add content
            for file in content_files:
                segment = AudioSegment.from_mp3(file)
                if ConstellationConfig.AUDIO_SETTINGS["normalize_audio"]:
                    segment = effects.normalize(segment)
                combined += pause + segment
            
            # Add outro
            combined += pause + outro
            
            # Export the final audio
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            combined.export(output_file, format="mp3")
            
            logging.info(f"Created podcast with pre-recorded intro/outro: {output_file}")
            return output_file
            
        except Exception as e:
            logging.error(f"Error merging with pre-recorded intro/outro: {e}")
            return None
    
    def get_voice_config(self, language: str, speaker: str) -> Dict:
        """Get voice configuration for a speaker
        
        Args:
            language: Language code
            speaker: Speaker identifier
            
        Returns:
            Voice configuration dictionary
        """
        if language not in ConstellationConfig.VOICE_LIBRARY:
            raise ValueError(f"No voice library available for language: {language}")
            
        if speaker not in ConstellationConfig.VOICE_LIBRARY[language]:
            # Try with lowercase
            speaker = speaker.lower()
            if speaker not in ConstellationConfig.VOICE_LIBRARY[language]:
                raise ValueError(f"No voice configuration available for speaker: {speaker}")
        
        voice_info = ConstellationConfig.VOICE_LIBRARY[language][speaker]
        
        return {
            "voice_id": voice_info["id"],
            "model": ConstellationConfig.ELEVENLABS_MODELS["standard"],
            "settings": {
                "stability": 0.35,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }

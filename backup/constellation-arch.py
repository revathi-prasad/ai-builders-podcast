#!/usr/bin/env python3
"""
AI Builders Podcast: Fresh Constellation System Implementation
No migration needed - start clean with the new architecture
"""

import os
import json
import time
import random
import requests
import anthropic
from pydub import AudioSegment, effects
import argparse
import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Language(Enum):
    ENGLISH = "english"
    HINDI = "hindi"
    TAMIL = "tamil"
    TELUGU = "telugu"

class EpisodeType(Enum):
    BUILD = "build"           # Full technical build episodes
    SUMMARY = "summary"       # Insight extraction episodes
    INTERVIEW = "interview"   # Guest conversations
    QUICK_TIP = "quick_tip"  # Short social media clips

@dataclass
class EpisodeContext:
    """Configuration for episode generation"""
    topic: str
    primary_language: Language
    secondary_languages: List[Language]
    episode_type: EpisodeType
    target_duration: int  # minutes
    cost_tier: str       # "economy", "standard", "premium"
    cultural_focus: str  # e.g., "startup_ecosystem", "traditional_business"

class ConstellationConfig:
    """Central configuration for the Constellation System"""
    
    # API Keys - Update these with your actual keys
    CLAUDE_API_KEY = "your_claude_api_key"
    ELEVENLABS_API_KEY = "your_elevenlabs_api_key"
    
    # Model Selection Based on Cost Tier
    CLAUDE_MODELS = {
        "economy": "claude-3-haiku-20240307",      # $0.25/1M tokens - for drafts
        "standard": "claude-3-sonnet-20240229",    # $3/1M tokens - for production
        "premium": "claude-3-opus-20240229"        # $15/1M tokens - for special content
    }
    
    ELEVENLABS_MODELS = {
        "economy": "eleven_turbo_v2",              # Faster, lower cost
        "standard": "eleven_multilingual_v2",      # High quality, multilingual
        "premium": "eleven_multilingual_v2"        # Same as standard for now
    }
    
    # Voice Library - Update with your actual ElevenLabs voice IDs
    VOICE_LIBRARY = {
        "english": {
            "alex": {"id": "your_english_male_voice_id", "gender": "male"},
            "sarah": {"id": "your_english_female_voice_id", "gender": "female"}
        },
        "hindi": {
            "arjun": {"id": "your_hindi_male_voice_id", "gender": "male"},
            "priya": {"id": "your_hindi_female_voice_id", "gender": "female"}
        },
        "tamil": {
            "karthik": {"id": "your_tamil_male_voice_id", "gender": "male"},
            "meera": {"id": "your_tamil_female_voice_id", "gender": "female"}
        },
        "telugu": {
            "ravi": {"id": "your_telugu_male_voice_id", "gender": "male"},
            "lakshmi": {"id": "your_telugu_female_voice_id", "gender": "female"}
        }
    }
    
    # Cultural Context Database
    # This can also be customized by Podcast creators
    CULTURAL_CONTEXTS = {
        "english": {
            "business_focus": "global scalability, international best practices",
            "examples": ["Silicon Valley startups", "global SaaS companies"],
            "communication_style": "direct, data-driven, efficiency-focused",
            "tech_adoption": "early adopter, cutting-edge focus"
        },
        "hindi": {
            "business_focus": "MSMEs, digital transformation, tier-2/3 cities",
            "examples": ["local kirana stores", "textile businesses", "food delivery"],
            "communication_style": "relationship-first, practical examples",
            "tech_adoption": "gradual adoption, ROI-focused"
        },
        "tamil": {
            "business_focus": "manufacturing + tech, traditional industries + AI",
            "examples": ["automotive industry", "textile mills", "agricultural tech"],
            "communication_style": "detail-oriented, practical implementation",
            "tech_adoption": "conservative but thorough"
        },
        "telugu": {
            "business_focus": "emerging markets, Hyderabad tech ecosystem",
            "examples": ["pharma industry", "IT services", "emerging startups"],
            "communication_style": "balanced traditional and modern",
            "tech_adoption": "rapid growth, opportunity-focused"
        }
    }
    
    # Cost Control Settings
    MAX_DAILY_COST = 15.00  # Daily spending limit
    MAX_EPISODE_COST = 12.00  # Per episode limit
    CACHE_TTL_HOURS = 24  # How long to keep cached responses
    
    # Audio Settings
    AUDIO_SETTINGS = {
        "pause_between_turns": 800,  # milliseconds
        "quality": "high",
        "normalize_audio": True
    }

class IntelligentCache:
    """Caching system to reduce API costs"""
    
    def __init__(self, db_path: str = "constellation_cache.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for caching"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Claude response cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS claude_cache (
                cache_key TEXT PRIMARY KEY,
                response TEXT,
                model TEXT,
                timestamp DATETIME,
                token_count INTEGER,
                cost_estimate REAL
            )
        ''')
        
        # Audio file cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audio_cache (
                cache_key TEXT PRIMARY KEY,
                file_path TEXT,
                voice_id TEXT,
                char_count INTEGER,
                timestamp DATETIME,
                cost_estimate REAL
            )
        ''')
        
        # Cost tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cost_tracking (
                session_id TEXT,
                timestamp DATETIME,
                claude_cost REAL,
                elevenlabs_cost REAL,
                total_cost REAL,
                episode_topic TEXT,
                language TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_cached_claude_response(self, prompt: str, model: str) -> Optional[str]:
        """Get cached Claude response if available and fresh"""
        cache_key = hashlib.md5(f"{prompt}_{model}".encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT response, timestamp FROM claude_cache 
            WHERE cache_key = ?
        ''', (cache_key,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            response, timestamp = result
            cache_time = datetime.fromisoformat(timestamp)
            if datetime.now() - cache_time < timedelta(hours=ConstellationConfig.CACHE_TTL_HOURS):
                logging.info(f"Cache hit for Claude request - saved ~$0.05")
                return response
        
        return None
    
    def cache_claude_response(self, prompt: str, response: str, model: str, token_count: int):
        """Cache Claude response"""
        cache_key = hashlib.md5(f"{prompt}_{model}".encode()).hexdigest()
        cost_estimate = self._estimate_claude_cost(token_count, model)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO claude_cache 
            (cache_key, response, model, timestamp, token_count, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cache_key, response, model, datetime.now().isoformat(), token_count, cost_estimate))
        
        conn.commit()
        conn.close()
    
    def _estimate_claude_cost(self, token_count: int, model: str) -> float:
        """Estimate Claude API cost"""
        if "opus" in model:
            return token_count * 0.000015
        elif "sonnet" in model:
            return token_count * 0.000003
        else:
            return token_count * 0.00000025

class CulturalPersonalityEngine:
    """Creates culturally-adapted AI host personalities"""
    
    def __init__(self, cache: IntelligentCache):
        self.cache = cache
        self.claude_client = anthropic.Anthropic(api_key=ConstellationConfig.CLAUDE_API_KEY)
        
        # Define host personalities for each language
        # Please get this prompt from a google form so that this podcast system can be used by anyone
        # and the personalities can be updated easily
        self.personalities = {
            "english": {
                "alex": """You are Alex, a technical AI enthusiast from Bangalore. You're passionate about 
                building scalable solutions and connecting Indian innovation with global best practices. 
                Your style is energetic, practical, and you love diving into implementation details.""",
                
                "sarah": """You are Sarah, an AI researcher who bridges technology and society. 
                You're curious about human impact, ask thoughtful questions, and help make complex 
                topics accessible. You often explore the 'why' behind technical decisions."""
            },
            
            "hindi": {
                "arjun": """आप अर्जुन हैं, दिल्ली के एक तकनीकी विशेषज्ञ। आप भारतीय व्यापारिक चुनौतियों 
                को तकनीक से हल करने में विशेषज्ञ हैं। आपका फोकस व्यावहारिक समाधानों पर है जो छोटे और 
                मध्यम व्यापारियों के काम आ सकें।""",
                
                "priya": """आप प्रिया हैं, एक AI शोधकर्ता जो तकनीक और समाज के बीच सेतु का काम करती हैं। 
                आप हमेशा इस बात पर फोकस करती हैं कि नई तकनीक का आम लोगों पर क्या असर होगा।"""
            }
            
            # Add Tamil and Telugu personalities as needed
        }
    
    def generate_cultural_response(self, host: str, language: Language, topic: str, 
                                 context: str, cost_tier: str = "standard") -> str:
        """Generate culturally-adapted response from AI host"""
        
        model = ConstellationConfig.CLAUDE_MODELS[cost_tier]
        cultural_context = ConstellationConfig.CULTURAL_CONTEXTS[language.value]
        personality = self.personalities[language.value][host]
        
        prompt = f"""
{personality}

Cultural Context: {cultural_context['business_focus']}
Communication Style: {cultural_context['communication_style']}
Relevant Examples: {cultural_context['examples']}

Current Topic: {topic}
Conversation Context: {context}

Respond naturally in {language.value}, staying in character. Keep response 2-4 sentences, 
conversational and engaging. Include cultural references that resonate with your audience.
"""
        
        # Check cache first
        cached_response = self.cache.get_cached_claude_response(prompt, model)
        if cached_response:
            return cached_response
        
        try:
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=150,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            
            # Cache the response
            self.cache.cache_claude_response(
                prompt, content, model, 
                response.usage.input_tokens + response.usage.output_tokens
            )
            
            return content
            
        except Exception as e:
            logging.error(f"Error generating cultural response: {e}")
            return f"That's a fascinating perspective on {topic}."

class AudioProductionPipeline:
    """Handles audio generation with cost optimization"""
    
    def __init__(self, cache: IntelligentCache):
        self.cache = cache
        self.audio_queue = []
        
    def queue_audio_generation(self, text: str, voice_config: Dict, priority: str = "standard"):
        """Queue audio for batch processing"""
        self.audio_queue.append({
            "text": text,
            "voice_config": voice_config,
            "priority": priority,
            "timestamp": time.time()
        })
    
    def process_audio_batch(self) -> List[str]:
        """Process all queued audio efficiently"""
        if not self.audio_queue:
            return []
        
        logging.info(f"Processing batch of {len(self.audio_queue)} audio items...")
        
        # Sort by voice ID for efficiency
        self.audio_queue.sort(key=lambda x: x["voice_config"]["voice_id"])
        
        generated_files = []
        total_cost = 0.0
        
        for item in self.audio_queue:
            # Check cache first
            cache_key = hashlib.md5(
                f"{item['text']}_{item['voice_config']['voice_id']}".encode()
            ).hexdigest()
            
            cached_file = self._get_cached_audio(cache_key)
            if cached_file and os.path.exists(cached_file):
                generated_files.append(cached_file)
                logging.info("Audio cache hit - saved ~$1.50")
                continue
            
            # Generate new audio
            audio_file = self._generate_audio(item["text"], item["voice_config"])
            if audio_file:
                generated_files.append(audio_file)
                cost = len(item["text"]) * 0.00022
                total_cost += cost
                
                # Cache the audio file
                self._cache_audio(cache_key, audio_file, cost)
        
        logging.info(f"Audio batch processed - cost: ${total_cost:.2f}")
        self.audio_queue.clear()
        return generated_files
    
    def _generate_audio(self, text: str, voice_config: Dict) -> Optional[str]:
        """Generate audio using ElevenLabs"""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_config['voice_id']}"
        
        data = {
            "text": text,
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
    
    def _get_cached_audio(self, cache_key: str) -> Optional[str]:
        """Get cached audio file"""
        conn = sqlite3.connect(self.cache.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT file_path FROM audio_cache 
            WHERE cache_key = ?
        ''', (cache_key,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def _cache_audio(self, cache_key: str, file_path: str, cost: float):
        """Cache audio file reference"""
        conn = sqlite3.connect(self.cache.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO audio_cache 
            (cache_key, file_path, voice_id, char_count, timestamp, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cache_key, file_path, "voice_id", 0, datetime.now().isoformat(), cost))
        
        conn.commit()
        conn.close()

class ConstellationOrchestrator:
    """Main orchestrator for the Constellation System"""
    
    def __init__(self):
        self.cache = IntelligentCache()
        self.personality_engine = CulturalPersonalityEngine(self.cache)
        self.audio_pipeline = AudioProductionPipeline(self.cache)
        self.cost_tracker = {"claude": 0.0, "elevenlabs": 0.0, "total": 0.0}
    
    def generate_episode(self, context: EpisodeContext) -> Dict:
        """Generate complete episode with the Constellation System"""
        
        logging.info(f"Generating {context.episode_type.value} episode: {context.topic}")
        logging.info(f"Primary language: {context.primary_language.value}")
        logging.info(f"Cost tier: {context.cost_tier}")
        
        if context.episode_type == EpisodeType.BUILD:
            return self._generate_build_episode(context)
        elif context.episode_type == EpisodeType.SUMMARY:
            return self._generate_summary_episode(context)
        else:
            raise NotImplementedError(f"Episode type {context.episode_type} not yet implemented")
    
    def _generate_build_episode(self, context: EpisodeContext) -> Dict:
        """Generate a technical build episode"""
        
        # Plan conversation structure
        conversation_flow = self._plan_build_conversation(context)
        
        # Generate dialogue between hosts
        dialogue = []
        language = context.primary_language.value
        hosts = list(ConstellationConfig.VOICE_LIBRARY[language].keys())
        current_host = 0
        
        for turn_idx, conversation_point in enumerate(conversation_flow):
            host = hosts[current_host]
            
            # Generate culturally-adapted response
            response = self.personality_engine.generate_cultural_response(
                host=host,
                language=context.primary_language,
                topic=conversation_point["topic"],
                context=conversation_point["context"],
                cost_tier=context.cost_tier
            )
            
            dialogue.append({
                "speaker": host,
                "text": response,
                "timestamp": turn_idx
            })
            
            # Queue audio generation
            voice_config = self._get_voice_config(context.primary_language, host)
            self.audio_pipeline.queue_audio_generation(response, voice_config)
            
            current_host = 1 - current_host  # Alternate hosts
        
        # Process all audio
        audio_files = self.audio_pipeline.process_audio_batch()
        
        # Merge audio files
        output_file = f"{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
        final_audio = self._merge_audio_files(audio_files, output_file)
        
        return {
            "dialogue": dialogue,
            "audio_file": final_audio,
            "transcript": self._format_transcript(dialogue),
            "metadata": {
                "episode_type": context.episode_type.value,
                "language": context.primary_language.value,
                "topic": context.topic,
                "duration_estimate": len(dialogue) * 30,
                "cost_breakdown": self.cost_tracker.copy()
            }
        }
    
    def _plan_build_conversation(self, context: EpisodeContext) -> List[Dict]:
        """Plan the structure of a build episode"""
        
        # Basic conversation structure
        return [
            {"topic": f"Introduction to {context.topic}", "context": "episode_start"},
            {"topic": f"Problem analysis: {context.topic}", "context": "problem_exploration"},
            {"topic": f"Building solution for {context.topic}", "context": "solution_building"},
            {"topic": f"Testing our {context.topic} approach", "context": "testing_phase"},
            {"topic": f"Cultural considerations for {context.topic}", "context": "cultural_adaptation"},
            {"topic": f"Wrap-up: {context.topic} key insights", "context": "conclusion"}
        ]
    
    def _get_voice_config(self, language: Language, host: str) -> Dict:
        """Get voice configuration for a specific host"""
        voice_info = ConstellationConfig.VOICE_LIBRARY[language.value][host]
        
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
    
    def _merge_audio_files(self, filenames: List[str], output_file: str) -> str:
        """Merge audio files into final podcast"""
        if not filenames:
            return None
        
        combined = AudioSegment.from_mp3(filenames[0])
        combined = effects.normalize(combined)
        
        pause = AudioSegment.silent(duration=ConstellationConfig.AUDIO_SETTINGS["pause_between_turns"])
        
        for file in filenames[1:]:
            segment = AudioSegment.from_mp3(file)
            segment = effects.normalize(segment)
            combined += pause + segment
        
        combined = effects.normalize(combined)
        combined.export(output_file, format="mp3")
        
        logging.info(f"Created podcast: {output_file}")
        return output_file
    
    def _format_transcript(self, dialogue: List[Dict]) -> str:
        """Format dialogue as readable transcript"""
        transcript = []
        for entry in dialogue:
            transcript.append(f"{entry['speaker'].title()}: {entry['text']}")
        
        return "\n\n".join(transcript)
    
    def _generate_summary_episode(self, context: EpisodeContext) -> Dict:
        """Generate summary episode (to be implemented)"""
        # This would extract key insights and create shorter versions
        # for secondary languages
        pass

def main():
    """Main function to run the Constellation System"""
    parser = argparse.ArgumentParser(description="AI Builders Constellation System")
    parser.add_argument("--topic", required=True, help="Episode topic")
    parser.add_argument("--language", default="english", choices=["english", "hindi", "tamil", "telugu"])
    parser.add_argument("--type", default="build", choices=["build", "summary", "interview", "quick_tip"])
    parser.add_argument("--cost-tier", default="standard", choices=["economy", "standard", "premium"])
    parser.add_argument("--duration", type=int, default=45, help="Target duration in minutes")
    
    args = parser.parse_args()
    
    # Check API keys
    if ConstellationConfig.CLAUDE_API_KEY == "your_claude_api_key":
        print("⚠️ Please set your Claude API key in ConstellationConfig")
        return
    
    if ConstellationConfig.ELEVENLABS_API_KEY == "your_elevenlabs_api_key":
        print("⚠️ Please set your ElevenLabs API key in ConstellationConfig")
        return
    
    # Create episode context
    context = EpisodeContext(
        topic=args.topic,
        primary_language=Language(args.language),
        secondary_languages=[],  # Add secondary languages as needed
        episode_type=EpisodeType(args.type),
        target_duration=args.duration,
        cost_tier=args.cost_tier,
        cultural_focus="startup_ecosystem"  # Customize as needed
    )
    
    # Generate episode
    orchestrator = ConstellationOrchestrator()
    result = orchestrator.generate_episode(context)
    
    print(f"\n🎉 Episode generated successfully!")
    print(f"📁 Audio file: {result['audio_file']}")
    print(f"💰 Estimated cost: ${result['metadata']['cost_breakdown']['total']:.2f}")
    print(f"⏱️ Duration estimate: {result['metadata']['duration_estimate']} seconds")

if __name__ == "__main__":
    main()
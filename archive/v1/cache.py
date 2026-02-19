"""
Intelligent caching system for the AI Builders Podcast System
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import logging
import json
from config import ConstellationConfig

class IntelligentCache:
    """Caching system to reduce API costs
    
    This class provides a SQLite-based caching system for reducing API costs
    by storing and retrieving API responses, audio files, and other data.
    
    Attributes:
        db_path: Path to the SQLite database file
    """
    
    def __init__(self, db_path: str = "constellation_cache.db"):
        """Initialize the caching system
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for caching
        
        Creates the necessary tables for caching if they don't exist.
        """
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
        
        # Episode transcripts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS episode_transcripts (
                episode_id TEXT PRIMARY KEY,
                language TEXT,
                episode_type TEXT,
                topic TEXT,
                transcript TEXT,
                timestamp DATETIME
            )
        ''')
        
        # Research cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS research_cache (
                topic_key TEXT PRIMARY KEY,
                research_data TEXT,
                timestamp DATETIME,
                expiry DATETIME
            )
        ''')
        
        # Transformation cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transformation_cache (
                cache_key TEXT PRIMARY KEY,
                original_language TEXT,
                target_language TEXT,
                original_content TEXT,
                transformed_content TEXT,
                timestamp DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_cached_claude_response(self, prompt: str, model: str) -> Optional[str]:
        """Get cached Claude response if available and fresh
        
        Args:
            prompt: The prompt sent to Claude
            model: The Claude model used
            
        Returns:
            Cached response if available and fresh, None otherwise
        """
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
        """Cache Claude response
        
        Args:
            prompt: The prompt sent to Claude
            response: The response from Claude
            model: The Claude model used
            token_count: The number of tokens used
        """
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
        """Estimate Claude API cost
        
        Args:
            token_count: The number of tokens used
            model: The Claude model used
            
        Returns:
            Estimated cost in USD
        """
        if "opus" in model:
            return token_count * 0.000015
        elif "sonnet" in model:
            return token_count * 0.000003
        else:
            return token_count * 0.00000025
    
    def save_episode_transcript(self, episode_id: str, language: str, episode_type: str, 
                              topic: str, transcript: str):
        """Save episode transcript to database
        
        Args:
            episode_id: Unique identifier for the episode
            language: Language of the transcript
            episode_type: Type of episode
            topic: Topic of the episode
            transcript: Transcript text
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO episode_transcripts
            (episode_id, language, episode_type, topic, transcript, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (episode_id, language, episode_type, topic, transcript, 
              datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_episode_transcript(self, episode_id: str) -> Optional[Dict]:
        """Get episode transcript from database
        
        Args:
            episode_id: Unique identifier for the episode
            
        Returns:
            Dictionary containing transcript information, or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT language, episode_type, topic, transcript, timestamp 
            FROM episode_transcripts
            WHERE episode_id = ?
        ''', (episode_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            language, episode_type, topic, transcript, timestamp = result
            return {
                "language": language,
                "episode_type": episode_type,
                "topic": topic,
                "transcript": transcript,
                "timestamp": timestamp
            }
        
        return None
    
    def cache_audio_file(self, text: str, voice_id: str, file_path: str, char_count: int, cost_estimate: float):
        """Cache audio file information
        
        Args:
            text: Text used to generate the audio
            voice_id: Voice ID used
            file_path: Path to the generated audio file
            char_count: Character count of the text
            cost_estimate: Estimated cost of generation
        """
        cache_key = hashlib.md5(f"{text}_{voice_id}".encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO audio_cache
            (cache_key, file_path, voice_id, char_count, timestamp, cost_estimate)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cache_key, file_path, voice_id, char_count, datetime.now().isoformat(), cost_estimate))
        
        conn.commit()
        conn.close()
    
    def get_cached_audio_file(self, text: str, voice_id: str) -> Optional[str]:
        """Get cached audio file path if available
        
        Args:
            text: Text used to generate the audio
            voice_id: Voice ID used
            
        Returns:
            Path to cached audio file if available, None otherwise
        """
        cache_key = hashlib.md5(f"{text}_{voice_id}".encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT file_path FROM audio_cache
            WHERE cache_key = ?
        ''', (cache_key,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        
        return None
    
    def track_session_cost(self, session_id: str, claude_cost: float, elevenlabs_cost: float, 
                         episode_topic: str, language: str):
        """Track costs for a session
        
        Args:
            session_id: Unique identifier for the session
            claude_cost: Cost of Claude API usage
            elevenlabs_cost: Cost of ElevenLabs API usage
            episode_topic: Topic of the episode
            language: Language of the episode
        """
        total_cost = claude_cost + elevenlabs_cost
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO cost_tracking
            (session_id, timestamp, claude_cost, elevenlabs_cost, total_cost, episode_topic, language)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, datetime.now().isoformat(), claude_cost, elevenlabs_cost, 
              total_cost, episode_topic, language))
        
        conn.commit()
        conn.close()
    
    def get_daily_cost(self) -> float:
        """Get total cost for the current day
        
        Returns:
            Total cost in USD for the current day
        """
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time()).isoformat()
        today_end = datetime.combine(today, datetime.max.time()).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT SUM(total_cost) FROM cost_tracking
            WHERE timestamp BETWEEN ? AND ?
        ''', (today_start, today_end))
        
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            return float(result[0])
        
        return 0.0
    
    def cache_research_results(self, topic: str, research_data: Dict, ttl_hours: int = 168):
        """Cache research results
        
        Args:
            topic: Research topic
            research_data: Research data
            ttl_hours: Time-to-live in hours (default: 168 = 1 week)
        """
        topic_key = hashlib.md5(topic.lower().encode()).hexdigest()
        now = datetime.now()
        expiry = now + timedelta(hours=ttl_hours)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO research_cache
            (topic_key, research_data, timestamp, expiry)
            VALUES (?, ?, ?, ?)
        ''', (topic_key, json.dumps(research_data), now.isoformat(), expiry.isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_cached_research(self, topic: str) -> Optional[Dict]:
        """Get cached research results if available and not expired
        
        Args:
            topic: Research topic
            
        Returns:
            Cached research data if available and not expired, None otherwise
        """
        topic_key = hashlib.md5(topic.lower().encode()).hexdigest()
        now = datetime.now()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT research_data, expiry FROM research_cache
            WHERE topic_key = ?
        ''', (topic_key,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            research_data, expiry = result
            expiry_date = datetime.fromisoformat(expiry)
            
            if now < expiry_date:
                logging.info(f"Research cache hit for topic: {topic}")
                return json.loads(research_data)
        
        return None
    
    def cache_transformation(self, original_language: str, target_language: str, 
                           original_content: str, transformed_content: str):
        """Cache content transformation between languages
        
        Args:
            original_language: Original language code
            target_language: Target language code
            original_content: Original content
            transformed_content: Transformed content
        """
        cache_key = hashlib.md5(f"{original_language}_{target_language}_{original_content}".encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO transformation_cache
            (cache_key, original_language, target_language, original_content, transformed_content, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (cache_key, original_language, target_language, original_content, 
              transformed_content, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_cached_transformation(self, original_language: str, target_language: str, 
                               original_content: str) -> Optional[str]:
        """Get cached transformation if available
        
        Args:
            original_language: Original language code
            target_language: Target language code
            original_content: Original content
            
        Returns:
            Cached transformed content if available, None otherwise
        """
        cache_key = hashlib.md5(f"{original_language}_{target_language}_{original_content}".encode()).hexdigest()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT transformed_content FROM transformation_cache
            WHERE cache_key = ?
        ''', (cache_key,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            logging.info(f"Transformation cache hit: {original_language} -> {target_language}")
            return result[0]
        
        return None

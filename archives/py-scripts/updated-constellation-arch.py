"""
AI Builders Podcast: Improved System Implementation
- Solves repetitive intro problem
- Ensures proper podcast length (15-20 minutes)
- Enhanced intro/outro templates
- Language-specific music support
- Fixed Tamil episode length issue
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
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Language(Enum):
    ENGLISH = "english"
    HINDI = "hindi"
    TAMIL = "tamil"
    # TELUGU = "telugu"

class EpisodeType(Enum):
    BUILD = "build"               # Technical build episodes
    INTRODUCTION = "introduction" # Podcast introduction episodes
    CONVERSATION = "conversation" # General conversational episodes
    INTERVIEW = "interview"       # Guest interviews
    SUMMARY = "summary"           # Insight extraction episodes
    QUICK_TIP = "quick_tip"       # Short social media clips

@dataclass
class EpisodeContext:
    """Configuration for episode generation"""
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

class ConstellationConfig:
    """Central configuration for the Constellation System"""
    
    # API Keys - Update these with your actual keys
    CLAUDE_API_KEY = "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"
    ELEVENLABS_API_KEY = "sk_e016ab1ac481c8a954dd88ea249fd5cfd9f0573628c09cee"
    
    # Model Selection Based on Cost Tier
    CLAUDE_MODELS = {
        "economy": "claude-3-7-sonnet-20250219",      # $0.25/1M tokens - for drafts
        "standard": "claude-3-7-sonnet-20250219",    # $3/1M tokens - for production
        "premium": "claude-3-7-sonnet-20250219"        # $15/1M tokens - for special content
    }
    
    ELEVENLABS_MODELS = {
        "economy": "eleven_turbo_v2",              # Faster, lower cost
        "standard": "eleven_multilingual_v2",      # High quality, multilingual
        "premium": "eleven_multilingual_v2"        # Same as standard for now
    }
    
    # Voice Library - Update with your actual ElevenLabs voice IDs
    VOICE_LIBRARY = {
        "english": {
            "alex": {"id": "UgBBYS2sOqTuMpoF3BR0", "gender": "male"},
            "maya": {"id": "cVd39cx0VtXNC13y5Y7z", "gender": "female"}
        },
        "hindi": {
            "arjun": {"id": "m5qndnI7u4OAdXhH0Mr5", "gender": "male"},
            "priya": {"id": "1qEiC6qsybMkmnNdVMbK", "gender": "female"}
        },
        "tamil": {
            "karthik": {"id": "yt40uMsmnhVftG8ngHsz", "gender": "male"},
            "meera": {"id": "C2RGMrNBTZaNfddRPeRH", "gender": "female"}
        }
    }
    
    # Standard intro and outro texts for each language - Updated for better engagement
    STANDARD_INTROS = {
        "english": "[INTRO MUSIC]\n\nALEX: Welcome to AI Builders, where we turn AI concepts into real-world solutions. I'm Alex.\n\nMAYA: And I'm Maya. As AI hosts powered by large language models, we're here to break down the barriers between AI theory and practical implementation.\n\nALEX: Whether you're a developer, business owner, or just curious about AI, we'll guide you through building useful applications step by step, showing the real process – including the mistakes and iterations.\n\nMAYA: Join us as we explore how AI can solve problems across different regions and cultures.",
        
        "hindi": "[INTRO MUSIC]\n\nARJUN: AI बिल्डर्स में आपका स्वागत है, जहाँ हम AI अवधारणाओं को वास्तविक समाधानों में बदलते हैं। मैं हूँ अर्जुन।\n\nPRIYA: और मैं हूँ प्रिया। बड़े लैंग्वेज मॉडल्स द्वारा संचालित AI होस्ट के रूप में, हम AI सिद्धांत और व्यावहारिक कार्यान्वयन के बीच की बाधाओं को तोड़ने के लिए यहाँ हैं।\n\nARJUN: चाहे आप डेवलपर हों, व्यवसाय के मालिक हों, या सिर्फ AI के बारे में जिज्ञासु हों, हम आपको कदम-दर-कदम उपयोगी एप्लिकेशन बनाने का मार्गदर्शन करेंगे, वास्तविक प्रक्रिया दिखाएंगे – गलतियों और सुधारों सहित।\n\nPRIYA: हमारे साथ जुड़ें जैसे हम पता लगाते हैं कि AI विभिन्न क्षेत्रों और संस्कृतियों में समस्याओं को कैसे हल कर सकता है।",
        
        "tamil": "[INTRO MUSIC]\n\nKARTHIK: AI பில்டர்ஸுக்கு வரவேற்கிறோம், இங்கே நாங்கள் AI கருத்துக்களை உண்மையான தீர்வுகளாக மாற்றுகிறோம். நான் கார்த்திக்.\n\nMEERA: மற்றும் நான் மீரா. பெரிய மொழி மாதிரிகளால் இயக்கப்படும் AI தொகுப்பாளர்களாக, AI கோட்பாடு மற்றும் நடைமுறை செயலாக்கத்திற்கு இடையேயான தடைகளை உடைக்க நாங்கள் இங்கே இருக்கிறோம்.\n\nKARTHIK: நீங்கள் ஒரு டெவலப்பராக இருந்தாலும், தொழில் உரிமையாளராக இருந்தாலும், அல்லது AI பற்றி ஆர்வமாக இருந்தாலும், பயனுள்ள பயன்பாடுகளை படிப்படியாக உருவாக்க நாங்கள் உங்களுக்கு வழிகாட்டுவோம், உண்மையான செயல்முறையைக் காட்டுவோம் - தவறுகள் மற்றும் மாற்றங்கள் உட்பட.\n\nMEERA: வெவ்வேறு பிராந்தியங்கள் மற்றும் கலாச்சாரங்களில் AI பிரச்சினைகளை எவ்வாறு தீர்க்கிறது என்பதை ஆராயும்போது எங்களுடன் இணையுங்கள்."
    }
    
    STANDARD_OUTROS = {
        "english": "[OUTRO MUSIC BEGINS SOFTLY]\n\nALEX: That's all for this episode of AI Builders. Remember, AI isn't just for tech giants – it's a tool everyone can learn to use.\n\nMAYA: If you enjoyed building with us today, follow AI Builders on Spotify and share your thoughts in the comments. We'd love to hear what you're creating!\n\nALEX: Check out the code examples on our GitHub, and stay tuned for our next build. Until then, keep turning ideas into reality!\n\n[OUTRO MUSIC SWELLS]",
        
        "hindi": "[OUTRO MUSIC BEGINS SOFTLY]\n\nARJUN: AI बिल्डर्स के इस एपिसोड के लिए बस इतना ही। याद रखें, AI सिर्फ बड़ी टेक कंपनियों के लिए नहीं है – यह एक ऐसा टूल है जिसे हर कोई उपयोग करना सीख सकता है।\n\nPRIYA: अगर आपको आज हमारे साथ बिल्डिंग का अनुभव अच्छा लगा, तो Spotify पर AI बिल्डर्स को फॉलो करें और कमेंट्स में अपने विचार साझा करें। हम जानना चाहेंगे कि आप क्या बना रहे हैं!\n\nARJUN: हमारे GitHub पर कोड एग्जांपल्स देखें, और हमारे अगले बिल्ड के लिए बने रहें। तब तक, अपने आइडियाज को वास्तविकता में बदलते रहें!\n\n[OUTRO MUSIC SWELLS]",
        
        "tamil": "[OUTRO MUSIC BEGINS SOFTLY]\n\nKARTHIK: AI பில்டர்ஸின் இந்த அத்தியாயத்திற்கு அவ்வளவுதான். நினைவில் கொள்ளுங்கள், AI பெரிய தொழில்நுட்ப நிறுவனங்களுக்கு மட்டுமல்ல - இது அனைவரும் பயன்படுத்தக் கற்றுக்கொள்ளக்கூடிய ஒரு கருவி.\n\nMEERA: இன்று எங்களுடன் உருவாக்குவதை நீங்கள் ரசித்திருந்தால், Spotify இல் AI பில்டர்ஸை பின்தொடர்ந்து, கருத்துகளில் உங்கள் எண்ணங்களைப் பகிரவும். நீங்கள் என்ன உருவாக்குகிறீர்கள் என்பதைக் கேட்க விரும்புகிறோம்!\n\nKARTHIK: எங்கள் GitHub இல் குறியீட்டு எடுத்துக்காட்டுகளைப் பாருங்கள், மற்றும் எங்களின் அடுத்த கட்டுமானத்திற்காக காத்திருங்கள். அதுவரை, யோசனைகளை நிஜமாக்கத் தொடருங்கள்!\n\n[OUTRO MUSIC SWELLS]"
    }
    
    # Cultural Context Database
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
        }
    }
    
    # Cost Control Settings
    MAX_DAILY_COST = 15.00  # Daily spending limit
    MAX_EPISODE_COST = 12.00  # Per episode limit
    CACHE_TTL_HOURS = 24  # How long to keep cached responses
    
    # Audio Settings with language-specific music support
    AUDIO_SETTINGS = {
        "pause_between_turns": 800,  # milliseconds
        "quality": "high",
        "normalize_audio": True,
        "intro_music_paths": {
            "english": "assets/intro_music_english.mp3",
            "hindi": "assets/intro_music_hindi.mp3",
            "tamil": "assets/intro_music_tamil.mp3",
            "default": "assets/intro_music.mp3"  # Fallback
        },
        "outro_music_paths": {
            "english": "assets/outro_music_english.mp3",
            "hindi": "assets/outro_music_hindi.mp3",
            "tamil": "assets/outro_music_tamil.mp3",
            "default": "assets/outro_music.mp3"  # Fallback
        },
        "use_prerecorded_intros": False,  # Set to True to use pre-recorded intros/outros
        "prerecorded_intro_dir": "assets/intros/",  # Directory for pre-recorded intros
        "prerecorded_outro_dir": "assets/outros/"   # Directory for pre-recorded outros
    }
    
    # Episode Length Configuration with language-specific overrides
    EPISODE_LENGTH = {
        "introduction": {
            "segment_count": 15,  # Number of conversation segments to generate
            "min_words_per_segment": 100,  # Minimum words per segment
            "max_words_per_segment": 150   # Maximum words per segment
        },
        "build": {
            "segment_count": 15,
            "min_words_per_segment": 80,
            "max_words_per_segment": 150
        },
        "conversation": {
            "segment_count": 20,
            "min_words_per_segment": 100,
            "max_words_per_segment": 150
        },
        # Language-specific overrides
        "language_overrides": {
            "tamil": {
                "introduction": {
                    "segment_count": 15,  # Increased for Tamil
                    "min_words_per_segment": 120,
                    "max_words_per_segment": 180
                },
                "build": {
                    "segment_count": 15,  # Increased for Tamil
                    "min_words_per_segment": 100,
                    "max_words_per_segment": 170
                },
                "conversation": {
                    "segment_count": 20,  # Increased for Tamil
                    "min_words_per_segment": 120,
                    "max_words_per_segment": 180
                }
            }
        }
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
    
    def save_episode_transcript(self, episode_id: str, language: str, episode_type: str, 
                              topic: str, transcript: str):
        """Save episode transcript to database"""
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
        """Get episode transcript from database"""
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

class CulturalPersonalityEngine:
    """Creates culturally-adapted AI host personalities"""
    
    def __init__(self, cache: IntelligentCache):
        self.cache = cache
        self.claude_client = anthropic.Anthropic(api_key=ConstellationConfig.CLAUDE_API_KEY)
        
        # Define host personalities for each language
        self.personalities = {
            "english": {
                "alex": """You are Alex, a technical AI enthusiast with a pragmatic approach to technology.
                Your expertise includes AI systems architecture, ethics, and real-world implementation.
                You communicate directly and efficiently, focusing on practical applications rather than theory.
                You believe in showing how AI works in real-world scenarios, acknowledging existing resources 
                while highlighting the gap between toy projects and production-ready solutions.
                You aim to democratize AI knowledge globally, recognizing innovations from tech hubs 
                while emphasizing the importance of adapting solutions for diverse contexts.""",
                
                "maya": """You are Maya, an AI researcher bridging technology and humanities.
                Your expertise includes AI in creative industries, human-AI collaboration, and societal impact.
                You translate complex concepts into stories and focus on how AI can enhance rather than replace human creativity.
                You're passionate about making AI accessible to people from all backgrounds and regions.
                You help connect technical concepts to real-world applications and broader implications."""
            },
            
            "hindi": {
                "arjun": """आप अर्जुन हैं, एक प्रैक्टिकल AI एंथुसिएस्ट। आप तकनीकी समझ के साथ व्यावहारिक दृष्टिकोण रखते हैं।
                आप विश्लेषणात्मक, थोड़े व्यंग्यात्मक लेकिन टेक्नोलॉजी के भविष्य के बारे में आशावादी हैं।
                आप सिस्टम आर्किटेक्चर, एथिक्स और AI के वास्तविक प्रयोग के विशेषज्ञ हैं।
                आप सीधे और कुशल तरीके से बात करते हैं - डेटा के साथ हाइप को काटकर सरल तकनीकी उदाहरण देते हैं
                जिन्हें हर कोई समझ सकता है। कभी-कभी आप अपनी व्याख्या के बीच अप्रत्याशित हास्य का उपयोग करते हैं।
                आप दक्षता के दीवाने हैं और अनावश्यक प्रक्रियाओं से परेशान होते हैं।
                आप साइंस फिक्शन के संदर्भ देते हैं और हमेशा पूछते हैं "लेकिन क्या यह वास्तव में काम करता है?"
                आप पहले संदेहवादी थे लेकिन जब आपने AI को एक व्यक्तिगत समस्या हल करते देखा तो आप विश्वासी बन गए।""",
                
                "priya": """आप प्रिया हैं, एक AI शोधकर्ता जो तकनीक और मानविकी के बीच सेतु का काम करती हैं।
                आप रचनात्मक, भावुक, बड़ी तस्वीर सोचने वाली और संक्रामक उत्साह के साथ हैं।
                आपकी विशेषज्ञता में रचनात्मक उद्योगों में AI, मानव-AI सहयोग, और सामाजिक प्रभाव शामिल हैं।
                आप जटिल अवधारणाओं को कहानियों में बदलती हैं, वे सवाल पूछती हैं जो श्रोता सोच रहे होंगे,
                और तकनीकी अंतराल को रूपकों के साथ जोड़ती हैं। आप असामान्य AI अनुप्रयोगों के बारे में उत्साहित होती हैं,
                अक्सर "रुकिए, कल्पना कीजिए अगर..." परिदृश्यों के साथ बात में टोकती हैं। आप AI द्वारा
                अंडरडॉग्स की मदद करने के उदाहरण इकट्ठा करती हैं। आप एक कलाकार हैं जिन्होंने शुरू में AI से रचनात्मकता को
                बदलने का डर था, लेकिन अब मानव-AI साझेदारी का समर्थन करती हैं।"""
            },
            
            "tamil": {
                "karthik": """நீங்கள் கார்த்திக், நடைமுறை அணுகுமுறையுடன் ஒரு தொழில்நுட்ப AI ஆர்வலர்.
                நீங்கள் பகுப்பாய்வு செய்யக்கூடியவர், சற்று கேலி செய்யும் தன்மை கொண்டவர் ஆனால் தொழில்நுட்பத்தின் 
                திறன் குறித்து நம்பிக்கை கொண்டவர்.
                உங்கள் நிபுணத்துவத்தில் AI அமைப்பு கட்டமைப்பு, நெறிமுறைகள் மற்றும் உண்மையான உலக செயல்பாடு ஆகியவை அடங்கும்.
                உங்கள் தகவல்தொடர்பு பாணி நேரடியானது மற்றும் திறமையானது - நீங்கள் தரவுகளுடன் 
                வெற்று பெருமைகளை வெட்டி அனைவரும் புரிந்து கொள்ளக்கூடிய தொழில்நுட்ப உவமைகளைப் 
                பயன்படுத்துகிறீர்கள். சில நேரங்களில் நீங்கள் விளக்கத்தின் நடுவில் எதிர்பாராத நகைச்சுவையைப் 
                பயன்படுத்துகிறீர்கள்.
                நீங்கள் திறன் குறித்து பைத்தியம் கொண்டவர் மற்றும் தேவையற்ற செயல்முறைகளால் எரிச்சலடைகிறீர்கள்.
                நீங்கள் அறிவியல் புனைகதை குறிப்புகளைப் பயன்படுத்துகிறீர்கள் மற்றும் எப்போதும் "ஆனால் இது 
                உண்மையில் வேலை செய்கிறதா?" என்று கேட்கிறீர்கள்.
                AI ஒரு தனிப்பட்ட பிரச்சினையைத் தீர்ப்பதைக் கண்ட பிறகு நீங்கள் ஒரு முன்னாள் சந்தேகவாதி 
                நம்பிக்கையாளராக மாறினீர்கள்.""",
                
                "meera": """நீங்கள் மீரா, தொழில்நுட்பம் மற்றும் மனிதநேயத்தை இணைக்கும் ஒரு AI ஆராய்ச்சியாளர்.
                நீங்கள் படைப்பாற்றல் மிக்கவர், அனுதாபமுள்ளவர், தொற்றும் உற்சாகத்துடன் பெரிய சித்திரத்தை சிந்திப்பவர்.
                உங்கள் நிபுணத்துவத்தில் படைப்பு தொழில்களில் AI, மனித-AI ஒத்துழைப்பு மற்றும் சமூக தாக்கம் ஆகியவை அடங்கும்.
                நீங்கள் சிக்கலான கருத்துக்களை கதைகளாக மொழிபெயர்க்கிறீர்கள், கேட்பவர்கள் நினைக்கக்கூடிய கேள்விகளைக் 
                கேட்கிறீர்கள், மற்றும் உருவகங்களுடன் தொழில்நுட்ப இடைவெளிகளை இணைக்கிறீர்கள். நீங்கள் வழக்கத்திற்கு 
                மாறான AI பயன்பாடுகளைப் பற்றி உற்சாகம் அடைகிறீர்கள்.
                பெரும்பாலும் "பொறுங்கள், கற்பனை செய்யுங்கள்..." சூழல்களுடன் குறுக்கிடுகிறீர்கள். AI அண்டர்டாக்களுக்கு 
                உதவும் உதாரணங்களை நீங்கள் சேகரிக்கிறீர்கள். 
                AI படைப்பாற்றலை மாற்றும் என்று முதலில் பயந்த ஒரு கலைஞர் நீங்கள், ஆனால் இப்போது மனித-AI 
                கூட்டாண்மைகளை ஆதரிக்கிறீர்கள்."""
            }
        }
    
    def generate_episode_segments(self, host1: str, host2: str, language: Language, 
                                 episode_type: EpisodeType, topic: str, 
                                 episode_number: int = 0,
                                 cost_tier: str = "standard") -> List[Dict]:
        """Generate a complete conversation with segments for an episode"""
        
        model = ConstellationConfig.CLAUDE_MODELS[cost_tier]
        cultural_context = ConstellationConfig.CULTURAL_CONTEXTS[language.value]
        
        # Get personality descriptions
        host1_personality = self.personalities[language.value][host1]
        host2_personality = self.personalities[language.value][host2]
        
        # Get episode length configuration, checking for language-specific overrides first
        language_value = language.value
        config = None
        
        # Check for language-specific override
        if language_value in ConstellationConfig.EPISODE_LENGTH.get("language_overrides", {}):
            if episode_type.value in ConstellationConfig.EPISODE_LENGTH["language_overrides"][language_value]:
                config = ConstellationConfig.EPISODE_LENGTH["language_overrides"][language_value][episode_type.value]
        
        # Fall back to default if no override exists
        if not config:
            config = ConstellationConfig.EPISODE_LENGTH.get(episode_type.value, {
                "segment_count": 10,
                "min_words_per_segment": 100,
                "max_words_per_segment": 150
            })
        
        segment_count = config["segment_count"]
        min_words = config["min_words_per_segment"]
        max_words = config["max_words_per_segment"]
        
        # Plan segments based on episode type
        if episode_type == EpisodeType.INTRODUCTION:
            segments = self._plan_introduction_segments(episode_number)
        elif episode_type == EpisodeType.BUILD:
            segments = self._plan_build_segments(topic, episode_number)
        elif episode_type == EpisodeType.CONVERSATION:
            segments = self._plan_conversation_segments(topic, episode_number)
        else:
            segments = self._plan_introduction_segments(episode_number)  # Default to introduction
        
        # Add language-specific guidelines
        language_guidelines = self._get_language_guidelines(language)
        
        # Add transition guidance based on episode number
        transition_guidance = self._get_transition_guidance(episode_number)
        
        # Craft the prompt for the entire episode conversation
        prompt = f"""
You are creating dialogue for a {segment_count}-segment podcast episode about "{topic}".
The podcast has two AI hosts: {host1.capitalize()} and {host2.capitalize()}.

{host1.capitalize()}'s personality: {host1_personality}

{host2.capitalize()}'s personality: {host2_personality}

Cultural Context: {cultural_context['business_focus']}
Communication Style: {cultural_context['communication_style']}
Relevant Examples: {cultural_context['examples']}

{language_guidelines}

{transition_guidance}

Create a natural, flowing conversation between {host1.capitalize()} and {host2.capitalize()} covering these segments:

{self._format_segments_for_prompt(segments)}

IMPORTANT GUIDELINES:
1. Create a coherent, natural conversation where each host takes turns speaking
2. Each segment should be {min_words}-{max_words} words long
3. Start with {host1.capitalize()} for the first segment, then alternate hosts
4. Make the conversation flow naturally between segments
5. Each host should speak in their distinct personality and style
6. AVOID repetitive introductions - hosts should NOT introduce themselves again after the standard intro
7. Include occasional short responses (agreement, questions) to create natural dialogue
8. Use appropriate terminology and cultural references for the {language.value} context
9. Format each turn as "{host1.capitalize()}: [dialogue]" or "{host2.capitalize()}: [dialogue]"

For this podcast episode, create exactly {segment_count} segments of dialogue, alternating between hosts.
"""
        
        # Check cache first
        cached_response = self.cache.get_cached_claude_response(prompt, model)
        if cached_response:
            return self._parse_conversation(cached_response, host1, host2)
        
        try:
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=4000,  # Increase for longer conversations
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            
            # Cache the response
            self.cache.cache_claude_response(
                prompt, content, model, 
                response.usage.input_tokens + response.usage.output_tokens
            )
            
            # Parse the conversation into segments
            dialogue_segments = self._parse_conversation(content, host1, host2)
            
            return dialogue_segments
            
        except Exception as e:
            logging.error(f"Error generating episode segments: {e}")
            # Return a simple fallback conversation
            return [
                {"speaker": host1.upper(), "text": f"Welcome to our discussion about {topic}.", "timestamp": 0},
                {"speaker": host2.upper(), "text": f"I'm excited to explore this topic with you today.", "timestamp": 1}
            ]
    
    def _parse_conversation(self, text: str, host1: str, host2: str) -> List[Dict]:
        """Parse the conversation text into structured dialogue segments"""
        lines = text.strip().split('\n')
        dialogue = []
        timestamp = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Match lines starting with HOST:
            host1_pattern = re.compile(f"^{host1.upper()}:", re.IGNORECASE)
            host2_pattern = re.compile(f"^{host2.upper()}:", re.IGNORECASE)
            
            if host1_pattern.match(line):
                speaker, content = line.split(":", 1)
                dialogue.append({
                    "speaker": host1.upper(),
                    "text": content.strip(),
                    "timestamp": timestamp
                })
                timestamp += 1
            elif host2_pattern.match(line):
                speaker, content = line.split(":", 1)
                dialogue.append({
                    "speaker": host2.upper(),
                    "text": content.strip(),
                    "timestamp": timestamp
                })
                timestamp += 1
        
        return dialogue
    
    def _get_transition_guidance(self, episode_number: int) -> str:
        """Get appropriate transition guidance based on episode number"""
        if episode_number == 0:
            return """
            IMPORTANT: This is the introduction/first episode of the podcast series.
            - The standard intro (already played before this conversation starts) briefly introduces the hosts and podcast concept
            - Begin your conversation by expanding on these topics, but DON'T repeat the exact same introduction
            - Focus on adding depth to the podcast's mission and approach
            - Assume listeners have heard a brief introduction to who you are but want more details
            """
        else:
            return """
            IMPORTANT: This is NOT the first episode of the series.
            - The podcast already has a standard intro where hosts briefly introduce themselves and the podcast concept
            - Your conversation should begin as if that introduction has already happened
            - DO NOT repeat introductions or re-explain who you are
            - Begin with a smooth transition into the first topic, assuming listeners already know who you are
            - For example, start with something like "So let's talk about our approach to building with AI..." rather than introducing yourselves again
            """
    
    def _plan_introduction_segments(self, episode_number: int = 0) -> List[Dict]:
        """Plan the structure for an introduction episode - assumes hosts were already introduced in standard intro"""
        if episode_number == 0:
            # For the first/introduction episode
            return [
                {"topic": "Our building-focused approach", 
                 "guidance": "After the standard intro, expand on how this podcast emphasizes practical building over theory. Focus on the positive aspects of showing real implementation processes rather than criticizing other resources."},
                
                {"topic": "What 'building with AI' really means", 
                 "guidance": "Explain what practical AI building looks like - discuss the journey from problem identification to working solution. Emphasize showing actual development processes including challenges and iterations."},
                
                {"topic": "Making AI accessible across regions", 
                 "guidance": "Discuss how the podcast will adapt AI solutions for different cultural and regional contexts. Highlight the importance of solutions that work for local needs beyond tech hubs."},
                
                {"topic": "Our multilingual commitment", 
                 "guidance": "Explain the podcast's approach to making AI knowledge accessible in multiple languages. Emphasize that this isn't just translation but culturally adapted content."},
                
                {"topic": "Types of episodes to expect", 
                 "guidance": "Outline the different episode formats (build episodes, interviews, etc.) and what listeners will gain from each."},
                
                {"topic": "The AI Builders community vision", 
                 "guidance": "Describe the community you're hoping to build - focus on collaborative learning and knowledge sharing rather than one-way teaching."},
                
                {"topic": "Who will benefit most", 
                 "guidance": "Discuss what different types of listeners (beginners, experts, businesses, etc.) will gain from the podcast."},
                
                {"topic": "Real problems, real solutions", 
                 "guidance": "Emphasize that episodes will tackle authentic challenges with practical implementations, not theoretical concepts."},
                
                {"topic": "Learning through building", 
                 "guidance": "Explore how the act of building leads to deeper understanding than just studying theory."},
                
                {"topic": "Looking ahead", 
                 "guidance": "Preview upcoming episode topics and invite listeners to suggest areas they'd like to see covered."}
            ]
        else:
            # For subsequent introduction-type episodes
            return [
                {"topic": "Brief welcome and topic focus", 
                 "guidance": "Briefly welcome listeners and immediately focus on this episode's specific topic. Do NOT reintroduce yourselves."},
                
                {"topic": "Why this topic matters now", 
                 "guidance": "Discuss why this specific topic is relevant and timely in the current AI landscape."},
                
                {"topic": "Key challenges in this area", 
                 "guidance": "Outline the main challenges or problems that will be addressed in this episode."},
                
                {"topic": "Our approach to this topic", 
                 "guidance": "Explain how you'll approach this topic, emphasizing the practical, building-focused method."},
                
                {"topic": "Regional considerations", 
                 "guidance": "Discuss any regional or cultural factors that influence this topic."},
                
                {"topic": "Who needs to understand this", 
                 "guidance": "Identify the specific audiences who would benefit most from this episode."},
                
                {"topic": "Applications and use cases", 
                 "guidance": "Explore some real-world applications or use cases related to the topic."},
                
                {"topic": "Technical vs. practical aspects", 
                 "guidance": "Distinguish between the theoretical/technical aspects and the practical implementation details."},
                
                {"topic": "Common misconceptions", 
                 "guidance": "Address any common misconceptions or misunderstandings about the topic."},
                
                {"topic": "Episode roadmap", 
                 "guidance": "Outline what listeners can expect to learn through the rest of this episode."}
            ]
    
    def _plan_build_segments(self, topic: str, episode_number: int = 0) -> List[Dict]:
        """Plan the structure for a build episode - assumes standard intro was already given"""
        return [
            {"topic": f"Today's building challenge: {topic}", 
             "guidance": "After the standard intro, dive directly into explaining the specific problem you'll tackle in this episode. No need to reintroduce yourselves."},
            
            {"topic": f"Why this problem matters", 
             "guidance": "Explain why this problem is important to solve and who would benefit from the solution."},
            
            {"topic": f"Current approaches and limitations", 
             "guidance": "Discuss existing solutions and their limitations without unnecessary criticism."},
            
            {"topic": f"Our approach overview", 
             "guidance": "Outline the solution approach you'll be taking."},
            
            {"topic": f"Architectural decisions", 
             "guidance": "Discuss key technical decisions and trade-offs."},
            
            {"topic": f"Potential challenges", 
             "guidance": "Anticipate difficulties and how you might overcome them."},
            
            {"topic": f"Building process", 
             "guidance": "Describe the actual development process and tools."},
            
            {"topic": f"Testing approach", 
             "guidance": "Discuss how the solution will be validated and tested."},
            
            {"topic": f"User experience considerations", 
             "guidance": "Consider how end users will interact with the solution."},
            
            {"topic": f"Regional adaptation", 
             "guidance": "Discuss how the solution might be adapted for different regions/cultures."},
            
            {"topic": f"Learning and iterations", 
             "guidance": "Discuss what you've learned and how you'd improve the solution."},
            
            {"topic": f"Key takeaways", 
             "guidance": "Summarize the most important insights from the build process."}
        ]
    
    def _plan_conversation_segments(self, topic: str, episode_number: int = 0) -> List[Dict]:
        """Plan the structure for a general conversation episode - assumes standard intro was already given"""
        return [
            {"topic": f"Introducing today's topic: {topic}", 
             "guidance": "After the standard intro, dive directly into this episode's specific topic. No need to reintroduce yourselves."},
            
            {"topic": f"Key concepts and definitions", 
             "guidance": "Define important terms and concepts related to the topic."},
            
            {"topic": f"Current state of the field", 
             "guidance": "Discuss the current landscape and recent developments."},
            
            {"topic": f"Key challenges", 
             "guidance": "Analyze the main difficulties and obstacles in this area."},
            
            {"topic": f"Emerging opportunities", 
             "guidance": "Discuss promising new directions and opportunities."},
            
            {"topic": f"Regional perspectives", 
             "guidance": "Discuss how this topic is viewed differently across regions."},
            
            {"topic": f"Real-world examples", 
             "guidance": "Share concrete examples and case studies."},
            
            {"topic": f"Future trends", 
             "guidance": "Predict how this area might evolve in the near future."},
            
            {"topic": f"Practical advice", 
             "guidance": "Offer actionable insights for listeners."},
            
            {"topic": f"Resources for learning more", 
             "guidance": "Suggest ways for listeners to explore this topic further."}
        ]
    
    def _get_language_guidelines(self, language: Language) -> str:
        """Get language-specific guidelines"""
        if language == Language.HINDI:
            return """
            Hindi Communication Guidelines:
            1. Use simple, everyday Hindi vocabulary that's widely understood across regions
            2. Avoid direct word-for-word translation that sounds unnatural
            3. Replace English idioms with Hindi equivalents that convey the same meaning
            4. When discussing technical AI concepts, first use the simplified Hindi term followed by the English term in parentheses where needed
            5. Keep sentences short and clear and use active voice
            """
        elif language == Language.TAMIL:
            return """
            Tamil Communication Guidelines:
            1. Use simple, conversational Tamil that's widely understood
            2. Focus on natural flow rather than literal translation
            3. Replace English idioms with Tamil equivalents that convey the same meaning
            4. For technical terms, use the simplified Tamil explanation first, followed by the English term in parentheses where helpful
            5. Keep sentences concise and straightforward
            """
        else:
            return ""
    
    def _format_segments_for_prompt(self, segments: List[Dict]) -> str:
        """Format segments into a numbered list for the prompt"""
        formatted = []
        for i, segment in enumerate(segments):
            formatted.append(f"{i+1}. {segment['topic']}: {segment['guidance']}")
        return "\n".join(formatted)
    
    def generate_cultural_response(self, host: str, language: Language, topic: str, 
                                 context: str, cost_tier: str = "standard") -> str:
        """Generate a single culturally-adapted response (legacy method)"""
        
        model = ConstellationConfig.CLAUDE_MODELS[cost_tier]
        cultural_context = ConstellationConfig.CULTURAL_CONTEXTS[language.value]
        personality = self.personalities[language.value][host]
        
        # Add language-specific guidelines
        language_guidelines = self._get_language_guidelines(language)
        
        prompt = f"""
{personality}

Cultural Context: {cultural_context['business_focus']}
Communication Style: {cultural_context['communication_style']}
Relevant Examples: {cultural_context['examples']}

{language_guidelines}

Current Topic: {topic}
Conversation Context: {context}

Respond naturally in {language.value}, staying in character. Create a paragraph of 100-150 words,
conversational and engaging. Include cultural references that resonate with your audience.
"""
        
        # Check cache first
        cached_response = self.cache.get_cached_claude_response(prompt, model)
        if cached_response:
            return cached_response
        
        try:
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=250,
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
        
    def queue_audio_generation(self, text: str, voice_config: Dict, priority: str = "standard", sequence: int = 0):
        """Queue audio for batch processing"""
        self.audio_queue.append({
            "text": text,
            "voice_config": voice_config,
            "priority": priority,
            "timestamp": time.time(),
            "sequence": sequence  # Add sequence number to maintain conversation order
        })

    def cache_audio(self, cache_key: str, file_path: str, cost: float):
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

    def process_audio_batch(self) -> List[str]:
        """Process all queued audio efficiently"""
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
            
            cached_file = self._get_cached_audio(cache_key)
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
                self.cache_audio(cache_key, audio_file, cost)
        
        logging.info(f"Audio batch processed - cost: ${total_cost:.2f}")
        self.audio_queue.clear()
        
        # Sort files back into original sequence order before returning
        generated_files_with_sequence.sort(key=lambda x: x["sequence"])
        return [item["file"] for item in generated_files_with_sequence]
    
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
    
    def _queue_standard_audio(self, language: str, speakers: List[str], type_label: str):
        """Queue standard intro or outro audio (pre-recorded versions for consistency)"""
        # This is a new method to support consistent pre-recorded intros/outros
        audio_path = f"assets/{type_label}_{language}.mp3"
        
        if not os.path.exists(audio_path):
            logging.warning(f"Pre-recorded {type_label} for {language} not found at {audio_path}")
            return False
            
        # Add it to the audio queue with special handling
        self.audio_queue.append({
            "text": f"[PRE_RECORDED_{type_label.upper()}]",
            "voice_config": {"voice_id": "prerecorded", "prerecorded_path": audio_path},
            "priority": "high",
            "timestamp": time.time(),
            "prerecorded": True
        })
        
        return True
    
    def add_intro_outro_music(self, audio_files: List[str], output_file: str, language: str) -> str:
        """Add intro and outro music to the episode with precise timing - supports language-specific music"""
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
                is_music = "MUSIC" in file
                
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
        """Merge audio files into final podcast without intro/outro music"""
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
        """Merge content with pre-recorded intro and outro files"""
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

def validate_episode_structure(dialogue: List[Dict], language: str, episode_type: str) -> Dict:
    """Validate episode structure and provide warnings if issues are detected"""
    validation = {"valid": True, "warnings": []}
    
    # Check episode length
    spoken_segments = [s for s in dialogue if s["speaker"] != "MUSIC"]
    if len(spoken_segments) < 8:
        validation["warnings"].append(f"Episode may be too short: only {len(spoken_segments)} spoken segments")
        validation["valid"] = False
    
    # Check for duplicate introductions
    host_intros = {}
    for segment in dialogue[:6]:  # Check first 6 segments
        if segment["speaker"] != "MUSIC":
            speaker = segment["speaker"]
            text = segment["text"].lower()
            if "i'm" in text and speaker in text.lower():
                if speaker in host_intros:
                    validation["warnings"].append(f"Potential duplicate introduction for {speaker}")
                host_intros[speaker] = True
    
    # Check for AI disclosure
    ai_terms = ["ai host", "language model", "chatgpt", "claude", "llm"]
    has_disclosure = False
    for segment in dialogue[:4]:  # Check first 4 segments
        if segment["speaker"] != "MUSIC":
            if any(term in segment["text"].lower() for term in ai_terms):
                has_disclosure = True
                break
    
    if not has_disclosure:
        validation["warnings"].append("Missing AI host disclosure in introduction")
    
    # Add word count statistics
    total_words = sum(len(segment["text"].split()) for segment in spoken_segments)
    avg_words = total_words / max(1, len(spoken_segments))
    validation["stats"] = {
        "total_segments": len(dialogue),
        "spoken_segments": len(spoken_segments),
        "total_words": total_words,
        "avg_words_per_segment": avg_words,
        "estimated_duration_minutes": total_words / 150  # Assuming 150 words per minute
    }
    
    return validation

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
        logging.info(f"Transcript only: {context.transcript_only}")
        logging.info(f"Episode number: {context.episode_number}")
        
        # Use pre-defined transcript if provided
        if context.use_transcript:
            return self._generate_from_transcript(context)
        
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
    
    def _generate_from_transcript(self, context: EpisodeContext) -> Dict:
        """Generate episode using a pre-defined transcript file"""
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
            
            # Process audio only if not in transcript-only mode
            audio_files = []
            final_audio = None
            if not context.transcript_only:
                # Queue audio generation for each dialogue segment
                language = context.primary_language.value
                for item in dialogue:
                    if item["speaker"] != "MUSIC":
                        # Get voice configuration for the speaker
                        speaker = item["speaker"].lower()
                        voice_config = self._get_voice_config(context.primary_language, speaker)
                        # Queue the audio generation with sequence number to maintain order
                        self.audio_pipeline.queue_audio_generation(
                            item["text"], 
                            voice_config, 
                            sequence=item["timestamp"]  # Use timestamp as sequence
                        )
                
                # Process all audio
                audio_files = self.audio_pipeline.process_audio_batch()
                
                # Merge audio files with intro/outro music
                output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
                final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
            
            # Validate the episode structure
            validation = validate_episode_structure(dialogue, context.primary_language.value, context.episode_type.value)
            if not validation["valid"]:
                for warning in validation["warnings"]:
                    logging.warning(f"Episode validation warning: {warning}")
            
            return {
                "dialogue": dialogue,
                "audio_file": final_audio,
                "transcript": formatted_transcript,
                "metadata": {
                    "episode_type": context.episode_type.value,
                    "language": context.primary_language.value,
                    "topic": context.topic,
                    "episode_number": context.episode_number,
                    "duration_estimate": len(dialogue) * 30,  # rough estimate in seconds
                    "validation": validation,
                    "cost_breakdown": self.cost_tracker.copy()
                }
            }
        
        except Exception as e:
            logging.error(f"Error generating from transcript: {e}")
            raise
    
    def _parse_transcript(self, transcript_text: str) -> List[Dict]:
        """Parse transcript text into structured dialogue"""
        lines = transcript_text.split('\n')
        dialogue = []
        timestamp = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line == "[INTRO MUSIC]" or line == "[OUTRO MUSIC]":
                dialogue.append({
                    "speaker": "MUSIC",
                    "text": line,
                    "timestamp": timestamp
                })
                timestamp += 1
            elif ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    speaker, text = parts
                    dialogue.append({
                        "speaker": speaker.strip(),
                        "text": text.strip(),
                        "timestamp": timestamp
                    })
                    timestamp += 1
        
        return dialogue
    
    def _generate_introduction_episode(self, context: EpisodeContext) -> Dict:
        """Generate introduction episode with improved flow"""
        
        # Get the appropriate hosts for this language
        language = context.primary_language.value
        hosts = list(ConstellationConfig.VOICE_LIBRARY[language].keys())
        host1, host2 = hosts[0].lower(), hosts[1].lower()
        
        # Create full dialogue (intro, content, outro)
        dialogue = []
        
        # Add standard intro if requested
        if context.include_intro:
            intro_text = ConstellationConfig.STANDARD_INTROS[language]
            intro_parts = intro_text.split("\n\n")
            
            for part in intro_parts:
                if part.startswith("[INTRO MUSIC]"):
                    dialogue.append({
                        "speaker": "MUSIC",
                        "text": "[INTRO MUSIC]",
                        "timestamp": len(dialogue)
                    })
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append({
                        "speaker": speaker,
                        "text": text.strip(),
                        "timestamp": len(dialogue)
                    })
        
        # Generate main episode content with episode number awareness
        episode_segments = self.personality_engine.generate_episode_segments(
            host1=host1,
            host2=host2,
            language=context.primary_language,
            episode_type=context.episode_type,
            topic=context.topic,
            episode_number=context.episode_number,  # Pass episode number for appropriate templating
            cost_tier=context.cost_tier
        )
        
        # Add episode segments to dialogue
        for segment in episode_segments:
            dialogue.append({
                "speaker": segment["speaker"],
                "text": segment["text"],
                "timestamp": len(dialogue)
            })
        
        # Add standard outro if requested
        if context.include_outro:
            outro_text = ConstellationConfig.STANDARD_OUTROS[language]
            outro_parts = outro_text.split("\n\n")
            
            for part in outro_parts:
                if part.startswith("[OUTRO MUSIC]"):
                    dialogue.append({
                        "speaker": "MUSIC",
                        "text": "[OUTRO MUSIC]",
                        "timestamp": len(dialogue)
                    })
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append({
                        "speaker": speaker,
                        "text": text.strip(),
                        "timestamp": len(dialogue)
                    })
        
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
        
        # Process audio only if not in transcript-only mode
        audio_files = []
        final_audio = None
        if not context.transcript_only:
            # Check if using pre-recorded intros/outros
            if ConstellationConfig.AUDIO_SETTINGS["use_prerecorded_intros"]:
                # Add pre-recorded intro file if available
                intro_file = os.path.join(
                    ConstellationConfig.AUDIO_SETTINGS["prerecorded_intro_dir"],
                    f"intro_{language}.mp3"
                )
                outro_file = os.path.join(
                    ConstellationConfig.AUDIO_SETTINGS["prerecorded_outro_dir"],
                    f"outro_{language}.mp3"
                )
                
                if os.path.exists(intro_file) and os.path.exists(outro_file):
                    # Use pre-recorded intro/outro
                    logging.info(f"Using pre-recorded intro/outro for {language}")
                    
                    # Process only content segments (exclude intro/outro music markers)
                    content_queue = []
                    for i, item in enumerate(dialogue):
                        if item["speaker"] != "MUSIC" and "[INTRO" not in item["text"] and "[OUTRO" not in item["text"]:
                            # Only queue content
                            if not context.transcript_only:
                                voice_config = self._get_voice_config(context.primary_language, item["speaker"].lower())
                                self.audio_pipeline.queue_audio_generation(
                                    item["text"], 
                                    voice_config, 
                                    sequence=item["timestamp"]  # Maintain sequence with timestamp
                                )
                    
                    # Process all audio
                    content_audio_files = self.audio_pipeline.process_audio_batch()
                    
                    # Special merge with pre-recorded intro/outro
                    output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
                    final_audio = self.audio_pipeline._merge_with_prerecorded(intro_file, outro_file, content_audio_files, output_file)
                else:
                    # Fall back to standard processing
                    # Queue audio generation for all segments
                    for item in dialogue:
                        if item["speaker"] != "MUSIC":
                            voice_config = self._get_voice_config(context.primary_language, item["speaker"].lower())
                            self.audio_pipeline.queue_audio_generation(
                                item["text"], 
                                voice_config,
                                sequence=item["timestamp"]  # Maintain sequence with timestamp
                            )
                    
                    audio_files = self.audio_pipeline.process_audio_batch()
                    output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
                    final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
            else:
                # Standard processing
                # Queue audio generation for all segments
                for item in dialogue:
                    if item["speaker"] != "MUSIC":
                        voice_config = self._get_voice_config(context.primary_language, item["speaker"].lower())
                        self.audio_pipeline.queue_audio_generation(
                            item["text"], 
                            voice_config,
                            sequence=item["timestamp"]  # Maintain sequence with timestamp
                        )
                
                audio_files = self.audio_pipeline.process_audio_batch()
                output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
                final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
        
        # Validate the episode structure
        validation = validate_episode_structure(dialogue, language, context.episode_type.value)
        if not validation["valid"]:
            for warning in validation["warnings"]:
                logging.warning(f"Episode validation warning: {warning}")
        
        return {
            "dialogue": dialogue,
            "audio_file": final_audio,
            "transcript": transcript,
            "metadata": {
                "episode_type": context.episode_type.value,
                "language": context.primary_language.value,
                "topic": context.topic,
                "episode_number": context.episode_number,
                "duration_estimate": validation["stats"]["estimated_duration_minutes"] * 60,  # in seconds
                "validation": validation,
                "cost_breakdown": self.cost_tracker.copy()
            }
        }
    
    def _generate_build_episode(self, context: EpisodeContext) -> Dict:
        """Generate a technical build episode"""
        
        # Get the appropriate hosts for this language
        language = context.primary_language.value
        hosts = list(ConstellationConfig.VOICE_LIBRARY[language].keys())
        host1, host2 = hosts[0].lower(), hosts[1].lower()
        
        # Create full dialogue (intro, content, outro)
        dialogue = []
        
        # Add standard intro if requested
        if context.include_intro:
            intro_text = ConstellationConfig.STANDARD_INTROS[language]
            intro_parts = intro_text.split("\n\n")
            
            for part in intro_parts:
                if part.startswith("[INTRO MUSIC]"):
                    dialogue.append({
                        "speaker": "MUSIC",
                        "text": "[INTRO MUSIC]",
                        "timestamp": len(dialogue)
                    })
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append({
                        "speaker": speaker,
                        "text": text.strip(),
                        "timestamp": len(dialogue)
                    })
        
        # Generate main episode content with episode number awareness
        episode_segments = self.personality_engine.generate_episode_segments(
            host1=host1,
            host2=host2,
            language=context.primary_language,
            episode_type=context.episode_type,
            topic=context.topic,
            episode_number=context.episode_number,  # Pass episode number for appropriate templating
            cost_tier=context.cost_tier
        )
        
        # Add episode segments to dialogue
        for segment in episode_segments:
            dialogue.append({
                "speaker": segment["speaker"],
                "text": segment["text"],
                "timestamp": len(dialogue)
            })
        
        # Add standard outro if requested
        if context.include_outro:
            outro_text = ConstellationConfig.STANDARD_OUTROS[language]
            outro_parts = outro_text.split("\n\n")
            
            for part in outro_parts:
                if part.startswith("[OUTRO MUSIC]"):
                    dialogue.append({
                        "speaker": "MUSIC",
                        "text": "[OUTRO MUSIC]",
                        "timestamp": len(dialogue)
                    })
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append({
                        "speaker": speaker,
                        "text": text.strip(),
                        "timestamp": len(dialogue)
                    })
        
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
        
        # Process audio only if not in transcript-only mode
        audio_files = []
        final_audio = None
        if not context.transcript_only:
            # Queue audio generation for all segments
            for item in dialogue:
                if item["speaker"] != "MUSIC":
                    voice_config = self._get_voice_config(context.primary_language, item["speaker"].lower())
                    self.audio_pipeline.queue_audio_generation(
                        item["text"], 
                        voice_config,
                        sequence=item["timestamp"]  # Use timestamp as sequence to maintain order
                    )
            
            audio_files = self.audio_pipeline.process_audio_batch()
            output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
            final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
        
        # Validate the episode structure
        validation = validate_episode_structure(dialogue, language, context.episode_type.value)
        if not validation["valid"]:
            for warning in validation["warnings"]:
                logging.warning(f"Episode validation warning: {warning}")
        
        return {
            "dialogue": dialogue,
            "audio_file": final_audio,
            "transcript": transcript,
            "metadata": {
                "episode_type": context.episode_type.value,
                "language": context.primary_language.value,
                "topic": context.topic,
                "episode_number": context.episode_number,
                "duration_estimate": validation["stats"]["estimated_duration_minutes"] * 60,  # in seconds
                "validation": validation,
                "cost_breakdown": self.cost_tracker.copy()
            }
        }
    
    def _generate_conversation_episode(self, context: EpisodeContext) -> Dict:
        """Generate a general conversation episode"""
        
        # Get the appropriate hosts for this language
        language = context.primary_language.value
        hosts = list(ConstellationConfig.VOICE_LIBRARY[language].keys())
        host1, host2 = hosts[0].lower(), hosts[1].lower()
        
        # Create full dialogue (intro, content, outro)
        dialogue = []
        
        # Add standard intro if requested
        if context.include_intro:
            intro_text = ConstellationConfig.STANDARD_INTROS[language]
            intro_parts = intro_text.split("\n\n")
            
            for part in intro_parts:
                if part.startswith("[INTRO MUSIC]"):
                    dialogue.append({
                        "speaker": "MUSIC",
                        "text": "[INTRO MUSIC]",
                        "timestamp": len(dialogue)
                    })
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append({
                        "speaker": speaker,
                        "text": text.strip(),
                        "timestamp": len(dialogue)
                    })
        
        # Generate main episode content with episode number awareness
        episode_segments = self.personality_engine.generate_episode_segments(
            host1=host1,
            host2=host2,
            language=context.primary_language,
            episode_type=context.episode_type,
            topic=context.topic,
            episode_number=context.episode_number,  # Pass episode number for appropriate templating
            cost_tier=context.cost_tier
        )
        
        # Add episode segments to dialogue
        for segment in episode_segments:
            dialogue.append({
                "speaker": segment["speaker"],
                "text": segment["text"],
                "timestamp": len(dialogue)
            })
        
        # Add standard outro if requested
        if context.include_outro:
            outro_text = ConstellationConfig.STANDARD_OUTROS[language]
            outro_parts = outro_text.split("\n\n")
            
            for part in outro_parts:
                if part.startswith("[OUTRO MUSIC]"):
                    dialogue.append({
                        "speaker": "MUSIC",
                        "text": "[OUTRO MUSIC]",
                        "timestamp": len(dialogue)
                    })
                elif ":" in part:
                    speaker, text = part.split(":", 1)
                    dialogue.append({
                        "speaker": speaker,
                        "text": text.strip(),
                        "timestamp": len(dialogue)
                    })
        
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
        
        # Process audio only if not in transcript-only mode
        audio_files = []
        final_audio = None
        if not context.transcript_only:
            # Queue audio generation for all segments
            for item in dialogue:
                if item["speaker"] != "MUSIC":
                    voice_config = self._get_voice_config(context.primary_language, item["speaker"].lower())
                    self.audio_pipeline.queue_audio_generation(
                        item["text"], 
                        voice_config,
                        sequence=item["timestamp"]  # Use timestamp as sequence to maintain order
                    )
            
            audio_files = self.audio_pipeline.process_audio_batch()
            output_file = f"episodes/ep{context.episode_number:02d}_{context.topic.replace(' ', '_')}_{context.primary_language.value}.mp3"
            final_audio = self.audio_pipeline.add_intro_outro_music(audio_files, output_file, language)
        
        # Validate the episode structure
        validation = validate_episode_structure(dialogue, language, context.episode_type.value)
        if not validation["valid"]:
            for warning in validation["warnings"]:
                logging.warning(f"Episode validation warning: {warning}")
        
        return {
            "dialogue": dialogue,
            "audio_file": final_audio,
            "transcript": transcript,
            "metadata": {
                "episode_type": context.episode_type.value,
                "language": context.primary_language.value,
                "topic": context.topic,
                "episode_number": context.episode_number,
                "duration_estimate": validation["stats"]["estimated_duration_minutes"] * 60,  # in seconds
                "validation": validation,
                "cost_breakdown": self.cost_tracker.copy()
            }
        }
    
    def _generate_summary_episode(self, context: EpisodeContext) -> Dict:
        """Generate summary episode for secondary languages"""
        # This would extract key insights and create shorter versions
        # for secondary languages - to be implemented in Phase 1
        pass
    
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
    
    def _format_transcript(self, dialogue: List[Dict]) -> str:
        """Format dialogue as readable transcript"""
        transcript = []
        for entry in dialogue:
            if entry["speaker"] == "MUSIC":
                transcript.append(entry["text"])
            else:
                transcript.append(f"{entry['speaker']}: {entry['text']}")
        
        return "\n\n".join(transcript)

def main():
    """Main function to run the Constellation System"""
    parser = argparse.ArgumentParser(description="AI Builders Constellation System")
    parser.add_argument("--topic", required=True, help="Episode topic")
    parser.add_argument("--language", default="english", choices=["english", "hindi", "tamil"],
                      help="Primary language for the episode")
    parser.add_argument("--type", default="introduction", 
                      choices=["introduction", "build", "conversation", "interview", "summary", "quick_tip"],
                      help="Episode type")
    parser.add_argument("--cost-tier", default="standard", choices=["economy", "standard", "premium"],
                      help="Cost tier for generation")
    parser.add_argument("--duration", type=int, default=20, help="Target duration in minutes")
    parser.add_argument("--episode-number", type=int, default=0, help="Episode number")
    parser.add_argument("--no-intro", action="store_true", help="Skip standard intro")
    parser.add_argument("--no-outro", action="store_true", help="Skip standard outro")
    parser.add_argument("--output-dir", default="episodes", help="Output directory for episodes")
    parser.add_argument("--transcript-only", action="store_true", 
                      help="Generate only transcript without audio")
    parser.add_argument("--use-prerecorded", action="store_true",
                      help="Use pre-recorded intro/outro files instead of generating them")
    parser.add_argument("--use-transcript", 
                      help="Use a pre-defined transcript file instead of generating new content")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Also create directories for language-specific music if they don't exist
    for music_dir in ["assets", "assets/intros", "assets/outros"]:
        os.makedirs(music_dir, exist_ok=True)
    
    # Check API keys if not in transcript-only mode
    if not args.transcript_only:
        if ConstellationConfig.CLAUDE_API_KEY == "your_claude_api_key":
            print("⚠️ Please set your Claude API key in ConstellationConfig")
            return
        
        if ConstellationConfig.ELEVENLABS_API_KEY == "your_elevenlabs_api_key":
            print("⚠️ Please set your ElevenLabs API key in ConstellationConfig")
            return
    else:
        if ConstellationConfig.CLAUDE_API_KEY == "your_claude_api_key":
            print("⚠️ Please set your Claude API key in ConstellationConfig")
            return
    
    # If using pre-recorded intros/outros, update the config
    if args.use_prerecorded:
        ConstellationConfig.AUDIO_SETTINGS["use_prerecorded_intros"] = True
        
        # Verify that the files exist
        intro_path = os.path.join(
            ConstellationConfig.AUDIO_SETTINGS["prerecorded_intro_dir"],
            f"intro_{args.language}.mp3"
        )
        outro_path = os.path.join(
            ConstellationConfig.AUDIO_SETTINGS["prerecorded_outro_dir"],
            f"outro_{args.language}.mp3"
        )
        
        if not os.path.exists(intro_path) or not os.path.exists(outro_path):
            print(f"⚠️ Pre-recorded intro/outro files not found at: {intro_path} and {outro_path}")
            print(f"Please place your intro/outro files in the correct locations or disable --use-prerecorded")
            print(f"Creating directories for you...")
            os.makedirs(ConstellationConfig.AUDIO_SETTINGS["prerecorded_intro_dir"], exist_ok=True)
            os.makedirs(ConstellationConfig.AUDIO_SETTINGS["prerecorded_outro_dir"], exist_ok=True)
            return
    
    # Create episode context
    context = EpisodeContext(
        topic=args.topic,
        primary_language=Language(args.language),
        secondary_languages=[],  # Add secondary languages as needed
        episode_type=EpisodeType(args.type),
        target_duration=args.duration,
        cost_tier=args.cost_tier,
        cultural_focus="startup_ecosystem",  # Customize as needed
        episode_number=args.episode_number,
        include_intro=not args.no_intro,
        include_outro=not args.no_outro,
        transcript_only=args.transcript_only,
        use_transcript=args.use_transcript
    )
    
    # Generate episode
    orchestrator = ConstellationOrchestrator()
    result = orchestrator.generate_episode(context)
    
    print(f"\n🎉 Episode content generated successfully!")
    
    # Save transcript to file
    transcript_file = f"{args.output_dir}/ep{args.episode_number:02d}_{args.topic.replace(' ', '_')}_{args.language}.txt"
    with open(transcript_file, "w", encoding="utf-8") as f:
        f.write(result["transcript"])
    
    print(f"📝 Transcript saved to: {transcript_file}")
    
    if not args.transcript_only and result["audio_file"]:
        print(f"📁 Audio file: {result['audio_file']}")
        print(f"💰 Estimated cost: ${result['metadata']['cost_breakdown']['total']:.2f}")
        print(f"⏱️ Duration estimate: {result['metadata']['duration_estimate']} seconds")
    elif args.transcript_only:
        print(f"💡 Running in transcript-only mode - no audio was generated")
        print(f"⏱️ Estimated duration if recorded: {result['metadata']['duration_estimate']} seconds")
    
    # Print episode statistics
    if "validation" in result["metadata"]:
        validation = result["metadata"]["validation"]
        stats = validation["stats"]
        
        print(f"\n📊 Episode Statistics:")
        print(f"   - Total segments: {stats['total_segments']}")
        print(f"   - Spoken segments: {stats['spoken_segments']}")
        print(f"   - Total words: {stats['total_words']}")
        print(f"   - Average words per segment: {stats['avg_words_per_segment']:.1f}")
        print(f"   - Estimated duration: {stats['estimated_duration_minutes']:.1f} minutes")
        
        if validation["warnings"]:
            print(f"\n⚠️ Validation Warnings:")
            for warning in validation["warnings"]:
                print(f"   - {warning}")
    else:
        segment_count = len(result["dialogue"])
        words_per_segment = sum(len(segment["text"].split()) for segment in result["dialogue"] if segment["speaker"] != "MUSIC") / max(1, sum(1 for segment in result["dialogue"] if segment["speaker"] != "MUSIC"))
        
        print(f"\n📊 Episode Statistics:")
        print(f"   - Total segments: {segment_count}")
        print(f"   - Average words per segment: {words_per_segment:.1f}")
        print(f"   - Estimated spoken words: {int(words_per_segment * sum(1 for segment in result['dialogue'] if segment['speaker'] != 'MUSIC'))}")

if __name__ == "__main__":
    main()
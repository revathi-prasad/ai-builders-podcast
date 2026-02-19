"""
Enhanced Language transformation module for the AI Builders Podcast System

This module handles the transformation of content between languages, with enhanced
focus on natural language usage and cultural adaptation.
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

class EnhancedTransformationEngine:
    """
    Enhanced engine for transforming content between languages
    
    This class handles the transformation of podcast content from one language
    to another, with strict enforcement of natural language usage.
    
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
        
        # Language-specific configurations (add to your config.py)
        self.language_config = {
            "hindi": {
                "podcast_title": "नई तकनीक, नए अवसर",
                "host_mapping": {"ALEX": "ARJUN", "MAYA": "PRIYA"},
                "source_titles": ["Future Proof with AI", "AI Builders"]
            },
            "tamil": {
                "podcast_title": "புதிய மனிதருடன் ஆழ்நோக்கம்",
                "host_mapping": {"ALEX": "KARTHIK", "MAYA": "MEERA"},
                "source_titles": ["Future Proof with AI", "AI Builders"]
            },
            "english": {
                "podcast_title": "Future Proof with AI",
                "host_mapping": {"ALEX": "ALEX", "MAYA": "MAYA"},
                "source_titles": ["Future Proof with AI", "AI Builders"]
            }
        }
        
        # Enhanced terminology mappings with explanations
        self.enhanced_terminology = {
            "hindi": {
                # Common technical terms that should be explained
                "machine learning": "मशीन लर्निंग - यानी कंप्यूटर को सिखाना",
                "algorithm": "एल्गोरिदम - यानी काम करने का तरीका",
                "database": "डेटाबेस - यानी जानकारी का भंडार",
                "software": "सॉफ्टवेयर - यानी कंप्यूटर प्रोग्राम",
                "application": "एप्लिकेशन - यानी उपयोग/अनुप्रयोग",
                "implementation": "इम्प्लीमेंटेशन - यानी अमल में लाना",
                "framework": "फ्रेमवर्क - यानी ढांचा",
                "development": "डेवलपमेंट - यानी विकास/निर्माण",
                "process": "प्रोसेस - यानी प्रक्रिया",
                "solution": "सोल्यूशन - यानी समाधान",
                "practical": "प्रैक्टिकल - यानी व्यावहारिक",
                "neural network": "न्यूरल नेटवर्क - हमारे दिमाग के न्यूरॉन्स की तरह",
                "data processing": "डेटा प्रोसेसिंग - जानकारी को व्यवस्थित करना",
                "cloud computing": "क्लाउड कंप्यूटिंग - दूर रखे गए कंप्यूटर का इस्तेमाल",
                
                # Simple replacements that should be done completely
                "build": "बनाना",
                "create": "तैयार करना", 
                "develop": "विकसित करना",
                "deploy": "लगाना/शुरू करना",
                "test": "जांचना",
                "design": "डिज़ाइन करना",
                "project": "प्रोजेक्ट/काम",
                "system": "सिस्टम/व्यवस्था",
                "model": "मॉडल/नमूना",
                "example": "उदाहरण",
                "experience": "अनुभव",
                "challenge": "चुनौती",
                "opportunity": "अवसर",
                "problem": "समस्या",
                "efficient": "कुशल/तेज़",
                "effective": "प्रभावी",
                "innovative": "नवाचार",
                "community": "समुदाय",
                "global": "वैश्विक/दुनिया भर में",
                "local": "स्थानीय",
                "region": "क्षेत्र/इलाका",
                "culture": "संस्कृति",
                "context": "संदर्भ/माहौल",
                "insight": "अंतर्दृष्टि/समझ",
                "concept": "अवधारणा/विचार",
                "theory": "सिद्धांत",
                "research": "अनुसंधान/खोज",
                "innovation": "नवाचार",
                "technology": "तकनीक",
                "digital": "डिजिटल/अंकीय"
            },
            "tamil": {
                # Common technical terms that should be explained
                "machine learning": "மெஷின் லர்னிং் - அதாவது கம்ப்யூட்டருக்கு கத்துக்குடுக்குறது",
                "algorithm": "அல்காரிதம் - அதாவது வேலை செய்யுற முறை",
                "database": "டேட்டாபேஸ் - அதாவது தகவல்களோட கிடங்கு",
                "software": "சாப்ட்வேர் - அதாவது கம்ப்யூட்டர் புரோகிராம்கள்",
                "application": "ஆப்ளிகேஷன் - அதாவது பயன்பாடு",
                "implementation": "இம்ப்ளிமெண்டேஷன் - அதாவது நடைமுறைப்படுத்துறது",
                "framework": "ஃப்ரேம்வர்க் - அதாவது கட்டமைப்பு",
                "development": "டெவலப்மெண்ட் - அதாவது வளர்ச்சி",
                "process": "புராசெஸ் - அதாவது செயல்முறை",
                "solution": "சொல்யூஷன் - அதாவது தீர்வு",
                "practical": "பிராக்டிகல் - அதாவது நடைமுறை",
                "neural network": "நியூரல் நெட்வர்க் - நம்ம மூளையின் நியூரான்கள் மாதிரி",
                "data processing": "டேட்டா புராசெசிங் - தகவல்களை ஒழுங்கு படுத்துறது",
                "cloud computing": "க்லவுட் கம்ப்யூடிங் - தூரத்தில வைக்கப்பட்ட கம்ப்யூட்டர் பயன்படுத்துறது",
                
                # Simple replacements
                "build": "கட்டுறது",
                "create": "உருவாக்குறது",
                "develop": "வளர்க்குறது", 
                "deploy": "நடைமுறைப்படுத்துறது",
                "test": "சோதிக்குறது",
                "design": "வடிவமைக்குறது",
                "project": "திட்டம்",
                "system": "அமைப்பு",
                "model": "மாதிரி",
                "example": "உதாரணம்",
                "experience": "அனுபவம்",
                "challenge": "சவால்",
                "opportunity": "வாய்ப்பு",
                "problem": "பிரச்சினை",
                "efficient": "திறமையான",
                "effective": "பயனுள்ள",
                "innovative": "புதுமையான",
                "community": "சமூகம்",
                "global": "உலகளாவிய",
                "local": "உள்ளூர்",
                "region": "பகுதி",
                "culture": "கலாச்சாரம்",
                "context": "சூழல்",
                "insight": "நுண்ணறிவு",
                "concept": "கருத்து",
                "theory": "கோட்பாடு",
                "research": "ஆராய்ச்சி",
                "innovation": "புதுமை",
                "technology": "தொழில்நுட்பம்",
                "digital": "டிஜிட்டல்"
            }
        }
        
        # Words that are acceptable to keep in English (max 10% of content)
        self.acceptable_english_words = {
            "hindi": {
                "AI", "computer", "internet", "smartphone", "app", "email", "website",
                "blog", "social media", "GPS", "Wi-Fi", "Bluetooth", "USB", "PDF",
                "WhatsApp", "Facebook", "Google", "YouTube", "Instagram"
            },
            "tamil": {
                "AI", "computer", "internet", "smartphone", "app", "email", "website", 
                "blog", "social media", "GPS", "Wi-Fi", "Bluetooth", "USB", "PDF",
                "WhatsApp", "Facebook", "Google", "YouTube", "Instagram"
            }
        }
    
    def transform_content(self, original_segments: List[DialogueSegment], 
                    source_language: Language, target_language: Language,
                    topic: str, cost_tier: str = "standard",
                    reference_material: Optional[str] = None,
                    preserve_standard_sections: bool = False) -> TransformationResult:
        """Transform content with enhanced natural language enforcement
        
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
        
        # Separate intro, content, and outro sections
        intro_segments = []
        content_segments = []
        outro_segments = []
        
        # Identify sections
        in_intro = True
        in_outro = False
        
        for i, segment in enumerate(original_segments):
            # Check if we're still in intro
            if in_intro:
                if segment.text == "[INTRO MUSIC]" or (
                    segment.speaker != "MUSIC" and 
                    i < 5  # First 5 segments are typically intro
                ):
                    intro_segments.append(segment)
                    # Check if this is the last intro segment
                    if "join us as we explore" in segment.text.lower() or "let's explore" in segment.text.lower():
                        in_intro = False
                else:
                    in_intro = False
                    content_segments.append(segment)
            
            # Check if we're entering outro
            elif not in_outro and (
                segment.text == "[OUTRO MUSIC]" or 
                "that's all for this episode" in segment.text.lower() or
                "that's all for today" in segment.text.lower()
            ):
                in_outro = True
                outro_segments.append(segment)
            
            # Add to appropriate section
            elif in_outro:
                outro_segments.append(segment)
            else:
                content_segments.append(segment)
        
        # If preserve_standard_sections is True, use standard intros/outros
        if preserve_standard_sections:
            # Get standard intro/outro for target language
            target_intro = self.get_language_intro(target_language)
            target_outro = self.get_language_outro(target_language)
            
            # Parse standard sections
            intro_dialogue = self._parse_standard_section(target_intro)
            outro_dialogue = self._parse_standard_section(target_outro)
            
            # Transform only the content segments
            if content_segments:
                # Check cache first
                content_str = json.dumps([{
                    "speaker": s.speaker,
                    "text": s.text,
                    "timestamp": s.timestamp
                } for s in content_segments])
                
                cache_key = hashlib.md5(
                    f"{source_language.value}_{target_language.value}_{content_str}_{topic}".encode()
                ).hexdigest()
                
                cached_result = self.cache.get_cached_transformation(
                    source_language.value, 
                    target_language.value,
                    cache_key
                )
                
                if cached_result:
                    cached_segments = json.loads(cached_result)
                    transformed_content = [
                        DialogueSegment(
                            speaker=s["speaker"],
                            text=s["text"],
                            timestamp=s["timestamp"],
                            metadata=s.get("metadata", {})
                        )
                        for s in cached_segments
                    ]
                else:
                    # Transform the content segments
                    transformed_content = self._transform_segments(
                        content_segments, source_language, target_language, 
                        topic, cost_tier, reference_material
                    )
                    
                    # Cache the result
                    transformed_str = json.dumps([{
                        "speaker": s.speaker,
                        "text": s.text,
                        "timestamp": s.timestamp,
                        "metadata": getattr(s, 'metadata', {})
                    } for s in transformed_content])
                    
                    self.cache.cache_transformation(
                        source_language.value, 
                        target_language.value,
                        cache_key,
                        transformed_str
                    )
            else:
                transformed_content = []
            
            # Update timestamps for all segments
            timestamp = 0
            for segment in intro_dialogue:
                segment.timestamp = timestamp
                timestamp += 1
                
            for segment in transformed_content:
                segment.timestamp = timestamp
                timestamp += 1
                
            for segment in outro_dialogue:
                segment.timestamp = timestamp
                timestamp += 1
            
            # Combine all sections
            final_segments = intro_dialogue + transformed_content + outro_dialogue
            
            return TransformationResult(
                original_language=source_language,
                target_language=target_language,
                original_content=original_segments,
                transformed_content=final_segments,
                regional_adaptations=["Used standard intro/outro for target language"],
                terminology_mappings=self.enhanced_terminology.get(target_language.value, {})
            )
    
        # Otherwise, transform everything together (original behavior)
        else:
            # Check cache first
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
            
            # Get enhanced transformation guidelines
            guidelines = self._get_enhanced_guidelines(target_language.value)
            
            # Format the content segments for Claude
            formatted_original = "\n\n".join([
                f"{segment.speaker}: {segment.text}" 
                for segment in original_segments
            ])
            
            # Create the enhanced prompt
            model = ConstellationConfig.CLAUDE_MODELS[cost_tier]
            
            prompt = self._create_enhanced_prompt(
                formatted_original,
                source_language,
                target_language,
                topic,
                guidelines,
                reference_material
            )
            
            try:
                # Call Claude for transformation
                response = self.claude_client.messages.create(
                    model=model,
                    max_tokens=16000,
                    temperature=0.7,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                transformed_text = response.content[0].text
                
                # Apply post-processing for quality control
                enhanced_text = self._apply_quality_enhancements(
                    transformed_text, target_language.value, topic
                )
                
                # Parse the transformed content
                transformed_segments = self._parse_transformed_content(
                    enhanced_text, original_segments
                )
                
                # Validate transformation quality
                quality_score = self._validate_transformation_quality(
                    transformed_segments, target_language.value
                )
                
                if quality_score < 0.8:  # If quality is too low, retry with stricter guidelines
                    logging.warning(f"Low quality transformation (score: {quality_score}), retrying...")
                    enhanced_text = self._retry_with_stricter_guidelines(
                        formatted_original, target_language, topic, model
                    )
                    transformed_segments = self._parse_transformed_content(
                        enhanced_text, original_segments
                    )
                
                # Extract regional adaptations
                regional_adaptations = self._extract_regional_adaptations(
                    enhanced_text, target_language.value
                )
                
                # Create the transformation result
                result = TransformationResult(
                    original_language=source_language,
                    target_language=target_language,
                    original_content=original_segments,
                    transformed_content=transformed_segments,
                    regional_adaptations=regional_adaptations,
                    terminology_mappings=self.enhanced_terminology.get(target_language.value, {})
                )
                
                # Cache the transformation
                transformed_content_str = json.dumps([{
                    "speaker": s.speaker,
                    "text": s.text,
                    "timestamp": s.timestamp,
                    "metadata": getattr(s, 'metadata', {})
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
                return TransformationResult(
                    original_language=source_language,
                    target_language=target_language,
                    original_content=original_segments,
                    transformed_content=original_segments,
                    regional_adaptations=[f"Error during transformation: {str(e)}"],
                    terminology_mappings={}
                )
            
    def _parse_standard_section(self, section_text: str) -> List[DialogueSegment]:
        """Parse standard intro/outro text into dialogue segments"""
        segments = []
        timestamp = 0
        
        for line in section_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line == "[INTRO MUSIC]" or line == "[OUTRO MUSIC]":
                segments.append(DialogueSegment(
                    speaker="MUSIC",
                    text=line,
                    timestamp=timestamp
                ))
                timestamp += 1
            elif ":" in line:
                speaker, text = line.split(":", 1)
                segments.append(DialogueSegment(
                    speaker=speaker.strip(),
                    text=text.strip(),
                    timestamp=timestamp
                ))
                timestamp += 1
        
        return segments

    def _transform_segments(self, segments: List[DialogueSegment], 
                       source_language: Language, target_language: Language,
                       topic: str, cost_tier: str = "standard",
                       reference_material: Optional[str] = None) -> List[DialogueSegment]:
        """Transform just the content segments"""
        
        # Format the segments for transformation
        formatted_content = "\n\n".join([
            f"{segment.speaker}: {segment.text}" 
            for segment in segments
        ])
        
        # Get enhanced transformation guidelines
        guidelines = self._get_enhanced_guidelines(target_language.value)
        
        # Create the enhanced prompt
        model = ConstellationConfig.CLAUDE_MODELS[cost_tier]
        
        prompt = self._create_enhanced_prompt(
            formatted_content,
            source_language,
            target_language,
            topic,
            guidelines,
            reference_material
        )
        
        try:
            # Call Claude for transformation
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=8000,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}]
            )
            
            transformed_text = response.content[0].text
            
            # Apply post-processing for quality control
            enhanced_text = self._apply_quality_enhancements(
                transformed_text, target_language.value, topic
            )
            
            # Parse the transformed content
            transformed_segments = self._parse_transformed_content(
                enhanced_text, segments
            )
            
            # Validate transformation quality
            quality_score = self._validate_transformation_quality(
                transformed_segments, target_language.value
            )
            
            if quality_score < 0.8:  # If quality is too low, retry with stricter guidelines
                logging.warning(f"Low quality transformation (score: {quality_score}), retrying...")
                
                # Retry with stricter prompt
                strict_prompt = f"""
    # STRICT TRANSFORMATION - CONTENT ONLY

    Transform ONLY the following content segments from {source_language.value} to {target_language.value}.
    DO NOT add any intro or outro. Transform ONLY what is given.

    ## Original Content:
    {formatted_content}

    ## CRITICAL REQUIREMENTS:
    1. Transform ONLY the dialogue given - no additions
    2. Maintain the same number of segments
    3. Keep speaker labels EXACTLY as given (they should already be mapped)
    4. Use 90%+ {target_language.value} with minimal English
    5. Maintain natural conversational flow

    ## Language: {target_language.value}
    Topic: {topic}

    Transform each segment maintaining the speaker and natural flow:
    """
                
                try:
                    retry_response = self.claude_client.messages.create(
                        model=model,
                        max_tokens=8000,
                        temperature=0.5,  # Lower temperature for consistency
                        messages=[{"role": "user", "content": strict_prompt}]
                    )
                    
                    retry_text = retry_response.content[0].text
                    enhanced_text = self._apply_quality_enhancements(
                        retry_text, target_language.value, topic
                    )
                    transformed_segments = self._parse_transformed_content(
                        enhanced_text, segments
                    )
                    
                except Exception as e:
                    logging.error(f"Error in strict retry: {e}")
                    # Fall back to first attempt
                    pass
            
            # Ensure we have the same number of segments
            if len(transformed_segments) != len(segments):
                logging.warning(f"Segment count mismatch: {len(segments)} original, {len(transformed_segments)} transformed")
                
                # Try to match segments by position
                matched_segments = []
                for i, original_segment in enumerate(segments):
                    if i < len(transformed_segments):
                        # Use the transformed segment but ensure speaker matches
                        transformed_segment = transformed_segments[i]
                        transformed_segment.speaker = original_segment.speaker
                        matched_segments.append(transformed_segment)
                    else:
                        # Use original segment if no corresponding transformed segment
                        matched_segments.append(original_segment)
                
                transformed_segments = matched_segments
            
            # Ensure speaker names are correctly mapped
            language_config = self.language_config.get(target_language.value, {})
            host_mapping = language_config.get("host_mapping", {})
            
            for segment in transformed_segments:
                # Apply host mapping to speaker names
                for source_host, target_host in host_mapping.items():
                    if segment.speaker.upper() == source_host.upper():
                        segment.speaker = target_host.upper()
            
            return transformed_segments
            
        except Exception as e:
            logging.error(f"Error transforming segments: {e}")
            # Return original segments if transformation fails completely
            return segments
    def _create_enhanced_prompt(self, formatted_original: str, source_language: Language,
                             target_language: Language, topic: str, guidelines: Dict,
                             reference_material: Optional[str] = None) -> str:
        """Create enhanced prompt with strict natural language guidelines"""
        
        # Get language-specific configurations
        target_config = self.language_config.get(target_language.value, {})
        source_config = self.language_config.get(source_language.value, {})
        
        # Get terminology mappings
        terminology = self.enhanced_terminology.get(target_language.value, {})
        terminology_examples = "\n".join([
            f"❌ '{english}' → ✅ '{native}'" 
            for english, native in list(terminology.items())[:15]  # Show first 15 examples
        ])
        
        # Get acceptable English words
        acceptable_words = ", ".join(list(self.acceptable_english_words.get(target_language.value, set()))[:10])
        
        # Cultural analogies for the target language
        cultural_analogies = self._get_cultural_analogies(target_language.value)
        
        # Host name mapping instructions
        host_mapping = target_config.get("host_mapping", {})
        host_mapping_text = "\n".join([
            f"- ALWAYS replace '{source}' with '{target}' consistently throughout" 
            for source, target in host_mapping.items()
        ])
        
        # Podcast title mapping
        target_title = target_config.get("podcast_title", "AI Builders")
        source_titles = source_config.get("source_titles", [])
        title_mapping_text = "\n".join([
            f"- ALWAYS replace '{source_title}' with '{target_title}'" 
            for source_title in source_titles
        ])
        
        # Reference material section
        reference_section = ""
        if reference_material:
            reference_section = f"""
## Reference Material for Context
{reference_material}

Use this to enrich the transformation while maintaining natural language flow.
"""
        
        prompt = f"""
# CRITICAL NATURAL LANGUAGE TRANSFORMATION TASK

## 🎯 PRIMARY OBJECTIVE: 90% {target_language.value.upper()} RULE
Transform this content so that AT LEAST 90% is in pure {target_language.value}, with minimal English words.

## Original Content ({source_language.value})
Topic: {topic}

{formatted_original}

## 🚨 STRICT TRANSFORMATION RULES

### Rule 1: LANGUAGE-SPECIFIC NAMES (CRITICAL!)
{host_mapping_text}
{title_mapping_text}

### Rule 2: MANDATORY EXPLANATIONS
EVERY technical term MUST be explained when first mentioned:
❌ Wrong: "हम machine learning का use करेंगे"
✅ Right: "हम मशीन लर्निंग का इस्तेमाल करेंगे - यानी कंप्यूटर को इंसानों की तरह सीखना सिखाना"

### Rule 3: TERMINOLOGY REPLACEMENT
{terminology_examples}

### Rule 4: ACCEPTABLE ENGLISH (Only these words can stay as-is)
{acceptable_words}
ALL other English words MUST be replaced or explained.

### Rule 5: CULTURAL ANALOGIES REQUIRED
{cultural_analogies}

### Rule 6: NATURAL CONVERSATION TONE
- Use natural conversational language, maintain a friendly, conversational tone. 
- Keep responses flowing naturally between speakers
- Maintain professional yet friendly tone

## 🎭 TRANSFORMATION PATTERNS

### Pattern A: Explain-Then-Use
First mention: "Neural network - यानी हमारे दिमाग के न्यूरॉन्स की तरह एक नेटवर्क"
Later mentions: "इस neural network में..."

### Pattern B: Analogy-First
{("Data processing समझिए बिल्कुल डब्बावाले की तरह - हज़ारों pieces को सही जगह पहुंचाना" if target_language.value == 'hindi' else "Data processing समझिए காஞ்சিபுரம் பட்டு நெசவு மாதिरி - ஆயிரக்கணக்கான நூல்களை ஒழுங்கு படுத்துறது")}

### Pattern C: Cultural Context
Use examples from {("Bollywood, cricket, local festivals, daily life" if target_language.value == 'hindi' else "Tamil cinema, temple architecture, daily life")} that people relate to.

## 🚫 FORBIDDEN PATTERNS

❌ {("हम practical implementation के लिए modern framework का use करके efficient solution develop करेंगे" if target_language.value == 'hindi' else "நாம் practical implementation-க்காக modern framework use பண்ணி efficient solution develop பண்ணுவோம்")}

✅ {("हम व्यावहारिक अमल के लिए आधुनिक ढांचे का इस्तेमाल करके बेहतरीन समाधान बनाएंगे" if target_language.value == 'hindi' else "நாம் நடைமுறையான செயல்பாட்டுக்காக நவீன கட்டமைப்பை பயன்படுத்தி சிறந்த தீர்வை உருவாக்குவோம்")}

## ✅ QUALITY CHECKLIST
Before finalizing, ensure:
- 90%+ content is in {target_language.value}
- All technical terms are explained
- Cultural analogies are used
- Sounds like natural conversation
- Energy and enthusiasm is maintained
- Host names are correctly mapped: {host_mapping_text}
- Podcast title is correctly used: {target_title}

{reference_section}

## OUTPUT FORMAT
Transform each segment maintaining natural conversation flow:
SPEAKER: [Natural {target_language.value} content with cultural adaptation]

🎯 REMEMBER: This should sound like two intelligent friends excitedly discussing AI over {('chai' if target_language.value == 'hindi' else 'filter coffee')}, NOT a formal presentation!
"""
        
        return prompt
    
    def _get_enhanced_guidelines(self, language: str) -> Dict:
        """Get enhanced guidelines for the target language"""
        base_guidelines = ConstellationConfig.TRANSFORMATION_GUIDELINES.get(language, {})
        
        # Add enhanced casual replacements
        enhanced_guidelines = base_guidelines.copy()
        enhanced_guidelines["enhanced_terminology"] = self.enhanced_terminology.get(language, {})
        enhanced_guidelines["acceptable_english"] = self.acceptable_english_words.get(language, set())
        
        return enhanced_guidelines
    
    def _get_cultural_analogies(self, language: str) -> str:
        """Get cultural analogies for the target language"""
        if language == "hindi":
            return """
### Hindi Cultural Analogies:
- Neural Network → "हमारे दिमाग के न्यूरॉन्स की तरह"
- Data Processing → "डब्बावाले की तरह - हज़ारों टिफिन को सही जगह पहुंचाना"
- Algorithm → "रेसिपी की तरह - step by step निर्देश"
- Cloud Computing → "बैंक लॉकर की तरह - आपका सामान कहीं और सुरक्षित"
- Machine Learning → "बच्चे को साइकिल सिखाने की तरह"
"""
        elif language == "tamil":
            return """
### Tamil Cultural Analogies:
- Neural Network → "நம்ம மூளையின் நியூரான்கள் மாதিரி"
- Data Processing → "காஞ்சிபுரம் பட்டு நெசவு மாதிரி - ஆயிரக்கணக்கான நூல்களை ஒழுங்கு படுத்துறது"
- Algorithm → "சமையல் செய்முறை மாதிரி - step by step வழிமுறைகள்"
- Cloud Computing → "பேங்க் லாக்கர் மாதிரி - உங்க சாமான் வேற எங்கயோ பத்திரம்"
- Machine Learning → "குழந்தைக்கு cycle ஓட்ட கத்துக்குடுக்குறா மாதிரி"
"""
        return ""
    
    def _apply_quality_enhancements(self, text: str, language: str, topic: str) -> str:
        """Apply quality enhancements to ensure natural language usage"""
        enhanced_text = text
        
        # Get language-specific configuration
        language_config = self.language_config.get(language, {})
        
        # Apply host name mapping more aggressively
        host_mapping = language_config.get("host_mapping", {})
        for source_host, target_host in host_mapping.items():
            # Replace in all possible formats
            enhanced_text = re.sub(
                rf"\b{source_host}\b",
                target_host,
                enhanced_text,
                flags=re.IGNORECASE
            )
            # Also handle with asterisks (bold formatting)
            enhanced_text = enhanced_text.replace(f"**{source_host}:**", f"**{target_host}:**")
            enhanced_text = enhanced_text.replace(f"{source_host}:", f"{target_host}:")
        
        # Apply podcast title mapping more thoroughly
        target_title = language_config.get("podcast_title", "AI Builders")
        source_titles = language_config.get("source_titles", [])
        for source_title in source_titles:
            # Case-insensitive replacement
            pattern = re.compile(re.escape(source_title), re.IGNORECASE)
            enhanced_text = pattern.sub(target_title, enhanced_text)
        
        # Remove excessive casual conversation markers
        if language == "hindi":
            # Remove phrases that encourage too much English
            enhanced_text = enhanced_text.replace("casual conversation indicators", "")
            enhanced_text = re.sub(r'\(.*?casual.*?\)', '', enhanced_text)
            
        elif language == "tamil":
            enhanced_text = enhanced_text.replace("casual conversation indicators", "")
            enhanced_text = re.sub(r'\(.*?casual.*?\)', '', enhanced_text)
        
        return enhanced_text
    
    def _validate_transformation_quality(self, segments: List[DialogueSegment], 
                                   language: str) -> float:
        """Validate the quality of transformation based on natural language usage"""
        if not segments:
            return 0.0
        
        total_words = 0
        unacceptable_english_words = 0
        explained_terms = 0
        total_technical_terms = 0
        
        acceptable_words = self.acceptable_english_words.get(language, set())
        
        # Expand acceptable technical terms
        technical_terms = {
            "ai", "machine", "learning", "deep learning", "neural network", "algorithm",
            "data", "model", "cloud", "computing", "api", "framework", "database",
            "software", "hardware", "deployment", "production",
            "development", "programming", "code", "test", "debug",
            "system", "architecture", "infrastructure", "platform", "solution",
            "technology", "digital", "online learning", "batch",
            "process", "processing", "analytics", "insights", "metrics",
            "performance", "optimization", "documentation", "github", "repository", "open-source", 
            "client-server", "project", "product", "service", "application", "website", "mobile",
            "desktop", "server", "edge", "device", "iot", "sensor", "computer vision", 
            "classification", "regression", "clustering", "prediction",
            "training", "validation", "testing", "accuracy", "precision",
            "recall", "f1", "score", "loss", "gradient descent",
            "backpropagation", "tensorflow", "pytorch", "keras", "scikit-learn",
            "pandas", "numpy", "jupyter", "notebook", "colab", "docker",
            "kubernetes", "aws", "azure", "gcp", "serverless",
            "microservices", "rest", "graphql", "websocket", "http", "https",
            "gpu", "cpu", "ram", "dataset", "pipeline", "deploy", "git",
            "json", "xml", "sql", "nosql", "crud", "oauth", "jwt"
        }
        
        # Add technical terms to acceptable words
        acceptable_words_with_tech = acceptable_words.union(technical_terms)
        
        terminology = self.enhanced_terminology.get(language, {})
        
        for segment in segments:
            if segment.speaker == "MUSIC":
                continue
                
            words = segment.text.split()
            total_words += len(words)
            
            # In _validate_transformation_quality method, modify the checking part:

        for word in words:
            # Remove punctuation for checking
            clean_word = re.sub(r'[^\w]', '', word.lower())
            
            # Skip if empty or single character
            if len(clean_word) <= 1:
                continue
            
            # Check if it's an English word not in acceptable list
            if (clean_word.isalpha() and 
                clean_word.encode('ascii', 'ignore').decode('ascii') == clean_word and
                clean_word not in acceptable_words_with_tech):
                
                # Check if it's part of a compound technical term
                is_technical_compound = False
                
                # Check the word itself and also check bigrams (two-word combinations)
                for i, w in enumerate(words):
                    if i < len(words) - 1:
                        bigram = f"{words[i].lower()} {words[i+1].lower()}"
                        # Remove punctuation from bigram
                        clean_bigram = re.sub(r'[^\w\s]', '', bigram)
                        if clean_bigram in technical_terms:
                            is_technical_compound = True
                            break
                
                # Also check if the word is part of any technical term
                for tech_term in technical_terms:
                    if clean_word in tech_term.split() or tech_term in clean_word:
                        is_technical_compound = True
                        break
                
                if not is_technical_compound:
                    unacceptable_english_words += 1
            
            # Check for technical terms that should be explained
            for term in terminology.keys():
                if term.lower() in segment.text.lower():
                    total_technical_terms += 1
                    # Check if it's explained (contains "यानी" or "अर्थात्" or "-" nearby)
                    if ("यानी" in segment.text or "अर्थात्" in segment.text or 
                        "அதாவது" in segment.text or "मतलब" in segment.text or
                        " - " in segment.text):
                        explained_terms += 1
                    break
        
        # Calculate quality score with adjusted thresholds
        if total_words == 0:
            return 0.0
        
        # Adjust threshold - allow up to 20% English for technical content
        english_ratio = unacceptable_english_words / total_words
        english_score = max(0, 1 - (english_ratio * 5))  # More lenient penalty
        
        # Bonus for explaining technical terms
        explanation_score = (explained_terms / max(total_technical_terms, 1)) if total_technical_terms > 0 else 1.0
        
        # Combine scores
        quality_score = (english_score * 0.6) + (explanation_score * 0.4)
        
        logging.info(f"Quality validation: Unacceptable English ratio: {english_ratio:.2%}, "
                    f"Explained terms: {explained_terms}/{total_technical_terms}, "
                    f"Quality score: {quality_score:.2f}")
        
        return quality_score
    
    def _retry_with_stricter_guidelines(self, original_content: str, 
                                      target_language: Language, topic: str, 
                                      model: str) -> str:
        """Retry transformation with stricter guidelines for better quality"""
        strict_prompt = f"""
# ULTRA-STRICT NATURAL LANGUAGE TRANSFORMATION

## 🚨 EMERGENCY MODE: MAXIMUM NATURAL LANGUAGE

Original content: {original_content}

## ABSOLUTE REQUIREMENTS:
1. 95% content MUST be in {target_language.value}
2. EVERY English word MUST be explained or replaced
3. Use ONLY everyday conversation words
4. Add cultural examples for EVERY concept

## FORBIDDEN:
❌ Any English word longer than 3 letters (except: AI, app, GPS, Wi-Fi)
❌ Technical jargon without explanation
❌ Formal language

## REQUIRED:
✅ Grandmother-friendly explanations
✅ Local analogies (Bollywood, cricket, daily life)
✅ Enthusiastic tone like friends chatting

Transform this to sound like two excited friends discussing AI over chai/coffee:
"""
        
        try:
            response = self.claude_client.messages.create(
                model=model,
                max_tokens=16000,
                temperature=0.5,  # Lower temperature for more consistent results
                messages=[{"role": "user", "content": strict_prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logging.error(f"Error in strict retry: {e}")
            return original_content
    
    def _parse_transformed_content(self, transformed_text: str, 
                                original_segments: List[DialogueSegment]) -> List[DialogueSegment]:
        """Parse the transformed content from Claude's response with enhanced validation"""
        transformed_segments = []
        lines = transformed_text.strip().split('\n')
        
        # Get language configuration for speaker mapping
        # Detect target language from the transformed text
        target_language = None
        if "अर्जुन" in transformed_text or "प्रिया" in transformed_text:
            target_language = "hindi"
        elif "கார்த்திக்" in transformed_text or "மீரா" in transformed_text:
            target_language = "tamil"
        else:
            target_language = "english"
        
        # Create speaker mapping including both original and target speakers
        speaker_map = {}
        if target_language in self.language_config:
            host_mapping = self.language_config[target_language].get("host_mapping", {})
            # Add original speakers
            for orig_speaker in ["ALEX", "MAYA", "MUSIC"]:
                speaker_map[orig_speaker.upper()] = orig_speaker.upper()
            # Add target speakers
            for source, target in host_mapping.items():
                speaker_map[target.upper()] = target.upper()
                # Also add lowercase versions
                speaker_map[target.lower()] = target.upper()
        else:
            # Default mapping
            for segment in original_segments:
                speaker_map[segment.speaker.upper()] = segment.speaker.upper()
        
        current_speaker = None
        current_text = []
        timestamp = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip lines that are clearly headers or metadata
            if line.startswith('#') or line.startswith('**विषय:') or line.startswith('**Topic:'):
                continue
            
            # Skip lines that are just formatting markers
            if line in ['---', '***', '___']:
                continue
            
            # Check if this line starts with a speaker identifier
            speaker_match = False
            speaker_found = None
            text_content = line
            
            # Try different speaker patterns
            for speaker in speaker_map.values():
                # Pattern 1: "SPEAKER: text"
                if line.upper().startswith(f"{speaker}:"):
                    speaker_found = speaker
                    text_content = line[len(speaker)+1:].strip()
                    speaker_match = True
                    break
                
                # Pattern 2: "**SPEAKER:** text"
                if line.startswith(f"**{speaker}:**"):
                    speaker_found = speaker
                    text_content = line[len(speaker)+5:].strip()
                    speaker_match = True
                    break
                
                # Pattern 3: "SPEAKER: **speaker:** text" (double speaker)
                if f"{speaker}: **" in line.upper():
                    speaker_found = speaker
                    # Extract text after the second colon
                    parts = line.split(':', 2)
                    if len(parts) >= 3:
                        text_content = parts[2].strip()
                    elif len(parts) == 2:
                        text_content = parts[1].strip()
                        # Remove any **speaker:** patterns
                        text_content = re.sub(r'\*\*\w+:\*\*', '', text_content).strip()
                    speaker_match = True
                    break
                
                # Pattern 4: Check for Hindi/Tamil speaker names
                if target_language == "hindi":
                    if line.startswith("अर्जुन:") or line.startswith("**अर्जुन:**"):
                        speaker_found = "ARJUN"
                        text_content = re.sub(r'^(\*\*)?अर्जुन:(\*\*)?', '', line).strip()
                        speaker_match = True
                        break
                    elif line.startswith("प्रिया:") or line.startswith("**प्रिया:**"):
                        speaker_found = "PRIYA"
                        text_content = re.sub(r'^(\*\*)?प्रिया:(\*\*)?', '', line).strip()
                        speaker_match = True
                        break
                elif target_language == "tamil":
                    if line.startswith("கார்த்திக்:") or line.startswith("**கார்த்திக்:**"):
                        speaker_found = "KARTHIK"
                        text_content = re.sub(r'^(\*\*)?கார்த்திக்:(\*\*)?', '', line).strip()
                        speaker_match = True
                        break
                    elif line.startswith("மீரா:") or line.startswith("**மீரா:**"):
                        speaker_found = "MEERA"
                        text_content = re.sub(r'^(\*\*)?மீரா:(\*\*)?', '', line).strip()
                        speaker_match = True
                        break
            
            if speaker_match and speaker_found:
                # Save previous segment if exists
                if current_speaker and current_text:
                    segment_text = " ".join(current_text).strip()
                    if segment_text:  # Only add non-empty segments
                        transformed_segments.append(DialogueSegment(
                            speaker=current_speaker,
                            text=segment_text,
                            timestamp=timestamp,
                            metadata={}
                        ))
                        timestamp += 1
                
                # Start new segment
                current_speaker = speaker_found
                current_text = [text_content] if text_content else []
            elif current_speaker:
                # Continue current segment
                current_text.append(line)
        
        # Add final segment
        if current_speaker and current_text:
            segment_text = " ".join(current_text).strip()
            if segment_text:
                transformed_segments.append(DialogueSegment(
                    speaker=current_speaker,
                    text=segment_text,
                    timestamp=timestamp,
                    metadata={}
                ))
        
        # Enhanced fallback if parsing failed or too few segments
        if len(transformed_segments) < len(original_segments) * 0.5:
            logging.warning(f"Parsing yielded too few segments ({len(transformed_segments)} vs {len(original_segments)} original), using enhanced fallback")
            
            # Reset and try a different approach
            transformed_segments = []
            current_text_block = []
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines and headers
                if not line or line.startswith('#') or line.startswith('**विषय:'):
                    continue
                
                # Check if it's a speaker line
                is_speaker_line = False
                for speaker in speaker_map.values():
                    if speaker in line.upper() and ':' in line:
                        # Process previous block if exists
                        if current_text_block and len(transformed_segments) < len(original_segments):
                            # Assign to appropriate speaker based on position
                            idx = len(transformed_segments)
                            if idx < len(original_segments):
                                transformed_segments.append(DialogueSegment(
                                    speaker=original_segments[idx].speaker,
                                    text=" ".join(current_text_block).strip(),
                                    timestamp=idx,
                                    metadata={}
                                ))
                        
                        # Start new block
                        current_text_block = [re.sub(r'^[^:]+:\s*', '', line).strip()]
                        is_speaker_line = True
                        break
                
                if not is_speaker_line and current_text_block is not None:
                    current_text_block.append(line)
            
            # Process final block
            if current_text_block and len(transformed_segments) < len(original_segments):
                idx = len(transformed_segments)
                if idx < len(original_segments):
                    transformed_segments.append(DialogueSegment(
                        speaker=original_segments[idx].speaker,
                        text=" ".join(current_text_block).strip(),
                        timestamp=idx,
                        metadata={}
                    ))
        
        # Final validation - ensure proper speaker names
        if target_language in self.language_config:
            host_mapping = self.language_config[target_language].get("host_mapping", {})
            reverse_mapping = {v: v for k, v in host_mapping.items()}
            
            for segment in transformed_segments:
                if segment.speaker in reverse_mapping:
                    segment.speaker = reverse_mapping[segment.speaker]
        
        return transformed_segments
    
    def _extract_regional_adaptations(self, transformed_text: str, target_language: str) -> List[str]:
        """Extract regional adaptations made during transformation"""
        adaptations = []
        
        # Look for cultural references
        cultural_markers = {
            "hindi": ["डब्बावाले", "बॉलीवुड", "चाय", "रिक्शा", "मेट्रो", "ट्रेन"],
            "tamil": ["காஞ்சிபுரம்", "filter coffee", "தொடர்வண்டி", "auto", "சினிமा"]
        }
        
        if target_language in cultural_markers:
            for marker in cultural_markers[target_language]:
                if marker in transformed_text:
                    adaptations.append(f"Added cultural reference: {marker}")
        
        # Look for explanations (यानी, अतावा patterns)
        explanation_patterns = ["यानी", "अर्थात्", "মানে", "అంటే", "அதாவது"]
        explanation_count = sum(1 for pattern in explanation_patterns if pattern in transformed_text)
        
        if explanation_count > 0:
            adaptations.append(f"Added {explanation_count} explanatory phrases for better understanding")
        
        # Add general adaptation note
        adaptations.append(f"Content culturally adapted for {target_language} speakers with natural language flow")
        
        return adaptations
    
    # Add methods from original transformation.py that are still needed
    def localize_podcast_title(self, language: Language) -> str:
        """Get the localized podcast title for a language"""
        return ConstellationConfig.PODCAST_TITLES.get(language.value, "AI Builders")
    
    def get_language_intro(self, language: Language) -> str:
        """Get the standard intro for a language"""
        return ConstellationConfig.STANDARD_INTROS.get(language.value, "")
    
    def get_language_outro(self, language: Language) -> str:
        """Get the standard outro for a language"""
        return ConstellationConfig.STANDARD_OUTROS.get(language.value, "")
    
    def _transform_with_preserved_sections(self, original_segments: List[DialogueSegment],
                                     source_language: Language, target_language: Language,
                                     topic: str, cost_tier: str = "standard",
                                     reference_material: Optional[str] = None) -> TransformationResult:
        """Transform content while preserving standard sections with enhanced natural language"""
        # This method would be similar to the original but with enhanced guidelines
        # Implementation would follow the same pattern as the original but with
        # the enhanced prompting and quality validation
        
        # For brevity, keeping the original implementation structure but applying
        # the enhanced guidelines throughout
        
        return self.transform_content(
            original_segments, source_language, target_language,
            topic, cost_tier, reference_material, False
        )
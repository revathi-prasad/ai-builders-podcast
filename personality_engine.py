"""
Cultural Personality Engine for the AI Builders Podcast System

This module handles the generation of culturally-adapted AI host personalities
and conversations for podcast episodes.
"""

import json
import logging
import re
import time
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import anthropic

from config import ConstellationConfig, Language, EpisodeType
from models import DialogueSegment
from cache import IntelligentCache

class CulturalPersonalityEngine:
    """Creates culturally-adapted AI host personalities and conversations
    
    This class handles the generation of culturally-adapted AI host personalities
    and conversations for podcast episodes.
    
    Attributes:
        cache: Instance of IntelligentCache for caching responses
        claude_client: Anthropic Claude client
    """
    
    def __init__(self, cache: IntelligentCache):
        """Initialize the personality engine
        
        Args:
            cache: Instance of IntelligentCache for caching responses
        """
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
                                 podcast_title: str,
                                 episode_number: int = 0,
                                 cost_tier: str = "standard",
                                 research_data: Optional[Dict] = None,
                                 reference_material: Optional[str] = None) -> List[DialogueSegment]:
        """Generate a complete conversation with segments for an episode
        
        Args:
            host1: First host identifier
            host2: Second host identifier
            language: Episode language
            episode_type: Episode type
            topic: Episode topic
            podcast_title: Podcast title
            episode_number: Episode number
            cost_tier: Cost tier for Claude API
            research_data: Optional research data to inform the conversation
            reference_material: Optional reference material to enrich the conversation
            
        Returns:
            List of dialogue segments
        """
        
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
        
        # Include research data if provided
        research_section = ""
        if research_data:
            research_section = self._format_research_for_prompt(research_data)
        
        # Include reference material if provided
        reference_section = ""
        if reference_material:
            reference_section = f"""
## Reference Material
Use the following reference material to enrich the conversation:

{reference_material}
"""
        
        # Get region-specific examples
        regional_examples = ""
        if language.value in ConstellationConfig.REGIONAL_EXAMPLES:
            examples = ConstellationConfig.REGIONAL_EXAMPLES[language.value]
            regional_examples = "## Regional Examples to Include:\n"
            for concept, example in examples.items():
                regional_examples += f"- {concept}: {example}\n"
        
        # Craft the prompt for the entire episode conversation
        prompt = f"""
# Podcast Episode Generation

## Podcast Information
- Podcast Title: {podcast_title}
- Episode Topic: "{topic}"
- Language: {language.value}
- Episode Number: {episode_number}
- Episode Type: {episode_type.value}

## Host Personalities
### {host1.capitalize()}
{host1_personality}

### {host2.capitalize()}
{host2_personality}

## Cultural Context
- Business Focus: {cultural_context['business_focus']}
- Communication Style: {cultural_context['communication_style']}
- Relevant Examples: {', '.join(cultural_context['examples'])}
- Tech Adoption: {cultural_context['tech_adoption']}

{language_guidelines}

{transition_guidance}

{regional_examples}

{research_section}

{reference_section}

## Episode Structure
Create a natural, flowing conversation between {host1.capitalize()} and {host2.capitalize()} covering these segments:

{self._format_segments_for_prompt(segments)}

## Output Guidelines
1. Create a coherent, natural conversation where each host takes turns speaking
2. Each segment should be {min_words}-{max_words} words long
3. Start with {host1.capitalize()} for the first segment, then alternate hosts
4. Make the conversation flow naturally between segments
5. Each host should speak in their distinct personality and style
6. AVOID repetitive introductions - hosts should NOT introduce themselves again after the standard intro
7. Include occasional short responses (agreement, questions) to create natural dialogue
8. Use appropriate terminology and cultural references for the {language.value} context
9. Format each turn as "{host1.capitalize()}: [dialogue]" or "{host2.capitalize()}: [dialogue]"
10. Incorporate region-specific examples to explain complex AI concepts
11. If using research data, integrate it naturally without making the conversation feel academic

Generate exactly {segment_count} segments of dialogue, alternating between hosts.
"""
        
        # Check cache first
        cache_key = hashlib.md5(f"{prompt}_{model}".encode()).hexdigest()
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
                DialogueSegment(speaker=host1.upper(), text=f"Welcome to our discussion about {topic}.", timestamp=0),
                DialogueSegment(speaker=host2.upper(), text=f"I'm excited to explore this topic with you today.", timestamp=1)
            ]
    
    def _parse_conversation(self, text: str, host1: str, host2: str) -> List[DialogueSegment]:
        """Parse the conversation text into structured dialogue segments
        
        Args:
            text: Conversation text from Claude
            host1: First host identifier
            host2: Second host identifier
            
        Returns:
            List of dialogue segments
        """
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
                dialogue.append(DialogueSegment(
                    speaker=host1.upper(),
                    text=content.strip(),
                    timestamp=timestamp
                ))
                timestamp += 1
            elif host2_pattern.match(line):
                speaker, content = line.split(":", 1)
                dialogue.append(DialogueSegment(
                    speaker=host2.upper(),
                    text=content.strip(),
                    timestamp=timestamp
                ))
                timestamp += 1
        
        return dialogue
    
    def _get_transition_guidance(self, episode_number: int) -> str:
        """Get appropriate transition guidance based on episode number
        
        Args:
            episode_number: Episode number
            
        Returns:
            Transition guidance text
        """
        if episode_number == 0:
            return """
            ## Transition Guidance
            This is the introduction/first episode of the podcast series.
            - The standard intro (already played before this conversation starts) briefly introduces the hosts and podcast concept
            - Begin your conversation by expanding on these topics, but DON'T repeat the exact same introduction
            - Focus on adding depth to the podcast's mission and approach
            - Assume listeners have heard a brief introduction to who you are but want more details
            """
        else:
            return """
            ## Transition Guidance
            This is NOT the first episode of the series.
            - The podcast already has a standard intro where hosts briefly introduce themselves and the podcast concept
            - Your conversation should begin as if that introduction has already happened
            - DO NOT repeat introductions or re-explain who you are
            - Begin with a smooth transition into the first topic, assuming listeners already know who you are
            - For example, start with something like "So let's talk about our approach to building with AI..." rather than introducing yourselves again
            """
    
    def _plan_introduction_segments(self, episode_number: int = 0) -> List[Dict]:
        """Plan the structure for an introduction episode
        
        Args:
            episode_number: Episode number
            
        Returns:
            List of segment plans
        """
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
        """Plan the structure for a build episode
        
        Args:
            topic: Episode topic
            episode_number: Episode number
            
        Returns:
            List of segment plans
        """
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
        """Plan the structure for a general conversation episode
        
        Args:
            topic: Episode topic
            episode_number: Episode number
            
        Returns:
            List of segment plans
        """
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
        """Get language-specific guidelines
        
        Args:
            language: Language
            
        Returns:
            Language guidelines text
        """
        if language.value in ConstellationConfig.TRANSFORMATION_GUIDELINES:
            guidelines = ConstellationConfig.TRANSFORMATION_GUIDELINES[language.value]
            
            principles = "\n".join([f"- {p}" for p in guidelines["principles"]])
            
            return f"""
            ## Language Guidelines for {language.value}
            Style: {guidelines["style"]}
            
            ### Principles:
            {principles}
            """
        else:
            return ""
    
    def _format_segments_for_prompt(self, segments: List[Dict]) -> str:
        """Format segments into a numbered list for the prompt
        
        Args:
            segments: List of segment plans
            
        Returns:
            Formatted segments text
        """
        formatted = []
        for i, segment in enumerate(segments):
            formatted.append(f"{i+1}. {segment['topic']}: {segment['guidance']}")
        return "\n".join(formatted)
    
    def _format_research_for_prompt(self, research_data: Dict) -> str:
        """Format research data for inclusion in the prompt
        
        Args:
            research_data: Research data
            
        Returns:
            Formatted research text
        """
        research_text = """
## Research Data
Use the following research data to inform the conversation:

### Summary
{}

### Key Points
{}

### Examples
{}

### Regional Insights
{}
""".format(
            research_data.get("summary", ""),
            "\n".join([f"- {point}" for point in research_data.get("key_points", [])]),
            "\n".join([f"- {example}" for example in research_data.get("examples", [])]),
            "\n".join([f"#### {region}\n" + "\n".join([f"- {insight}" for insight in insights]) 
                      for region, insights in research_data.get("regional_insights", {}).items()])
        )
        
        return research_text
    
    def generate_cultural_response(self, host: str, language: Language, topic: str, 
                                 context: str, cost_tier: str = "standard") -> str:
        """Generate a single culturally-adapted response
        
        Args:
            host: Host identifier
            language: Language
            topic: Topic
            context: Conversation context
            cost_tier: Cost tier for Claude API
            
        Returns:
            Generated response
        """
        
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

"""
Script Generator Agent

This agent generates podcast scripts from Knowledge Graph content.
It uses the model-agnostic LLM interface to:
1. Query the Knowledge Graph for relevant facts
2. Structure content into natural dialogue
3. Apply cultural adaptation
4. Track fact citations for verification

Key Features:
- Multiple episode formats (conversation, interview, monologue)
- Cultural adaptation for different audiences
- Fact citation tracking
- Configurable personas
- Model-agnostic: Claude, Qwen, Llama, Groq, local models

Cost Comparison (per 10-min episode ~2K output tokens):
- Claude Sonnet: ~$0.03
- Together (Qwen 72B): ~$0.002
- Groq (Llama 70B): ~$0.002
- Local (Ollama): $0
"""

import os
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from src.models.state import (
    PodcastState,
    DialogueSegment,
    LightweightHandoff,
    ProcessingStatus
)
from src.llm import get_llm_client, LLMConfig, LLMProvider


@dataclass
class Persona:
    """A podcast host persona"""
    name: str
    style: str  # "analytical", "enthusiastic", "storyteller", etc.
    expertise: str  # Area of expertise
    voice_id: str  # For TTS later
    language: str = "english"


# Default personas
DEFAULT_PERSONAS = {
    "english": [
        Persona(
            name="Priya",
            style="enthusiastic",
            expertise="technology trends",
            voice_id="priya_en",
            language="english"
        ),
        Persona(
            name="Arjun",
            style="analytical",
            expertise="technical deep-dives",
            voice_id="arjun_en",
            language="english"
        )
    ],
    "hindi": [
        Persona(
            name="प्रिया",
            style="enthusiastic",
            expertise="technology trends",
            voice_id="priya_hi",
            language="hindi"
        ),
        Persona(
            name="अर्जुन",
            style="analytical",
            expertise="technical deep-dives",
            voice_id="arjun_hi",
            language="hindi"
        )
    ],
    "tamil": [
        Persona(
            name="பிரியா",
            style="enthusiastic",
            expertise="technology trends",
            voice_id="priya_ta",
            language="tamil"
        ),
        Persona(
            name="அர்ஜுன்",
            style="analytical",
            expertise="technical deep-dives",
            voice_id="arjun_ta",
            language="tamil"
        )
    ]
}


class ScriptGenerator:
    """
    Generate podcast scripts using any LLM provider.

    This class handles the creative generation of podcast dialogue
    from structured content in the Knowledge Graph.

    Supports:
    - Claude (Anthropic) - Best quality
    - Qwen (Together.ai) - Good quality, 10x cheaper
    - Llama (Groq) - Fast inference
    - Local (Ollama) - Free, runs locally
    """

    def __init__(
        self,
        llm_config: Optional[LLMConfig] = None,
        # Legacy parameters for backward compatibility
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3
    ):
        """
        Initialize the script generator.

        Args:
            llm_config: LLM configuration (recommended way)
            api_key: Legacy: Anthropic API key
            model: Legacy: model name
            max_retries: Max retries for API calls

        Usage:
            # Modern way - cheap experiments
            generator = ScriptGenerator(LLMConfig.cheap())

            # Modern way - quality output
            generator = ScriptGenerator(LLMConfig.quality())

            # Legacy way (backward compatible)
            generator = ScriptGenerator(api_key="...")
        """
        self.max_retries = max_retries
        self._client = None

        # Determine configuration
        if llm_config:
            self.llm_config = llm_config
        elif api_key or model:
            # Legacy: use provided api_key/model with Anthropic
            self.llm_config = LLMConfig(
                provider=LLMProvider.ANTHROPIC,
                model=model or "claude-sonnet-4-20250514",
                api_key=api_key,
                task_type="dialogue_generation"
            )
        else:
            # Default: use environment variable LLM_PROVIDER or anthropic
            self.llm_config = LLMConfig(task_type="dialogue_generation")

    def _ensure_client(self):
        """Lazy initialize LLM client"""
        if self._client is None:
            self._client = get_llm_client(self.llm_config)

    async def generate_script_async(
        self,
        facts: List[Dict[str, Any]],
        topics: List[str],
        target_duration_minutes: int = 10,
        episode_format: str = "conversation",
        language: str = "english",
        audience_level: str = "intermediate",
        cultural_context: Optional[str] = None
    ) -> List[DialogueSegment]:
        """
        Generate a podcast script from facts and topics (async version).

        Args:
            facts: List of facts from Knowledge Graph
            topics: Main topics to cover
            target_duration_minutes: Target episode length
            episode_format: "conversation", "interview", "monologue"
            language: Target language
            audience_level: "beginner", "intermediate", "expert"
            cultural_context: Additional cultural adaptation notes

        Returns:
            List of DialogueSegment objects
        """
        self._ensure_client()

        # Get personas for this language
        personas = DEFAULT_PERSONAS.get(language, DEFAULT_PERSONAS["english"])

        # Build the prompt
        prompt = self._build_generation_prompt(
            facts=facts,
            topics=topics,
            personas=personas,
            target_duration_minutes=target_duration_minutes,
            episode_format=episode_format,
            audience_level=audience_level,
            cultural_context=cultural_context
        )

        # Generate with LLM (model-agnostic)
        response = await self._call_llm_async(prompt)

        # Parse response into DialogueSegments
        segments = self._parse_script_response(response, personas)

        return segments

    def generate_script(
        self,
        facts: List[Dict[str, Any]],
        topics: List[str],
        target_duration_minutes: int = 10,
        episode_format: str = "conversation",
        language: str = "english",
        audience_level: str = "intermediate",
        cultural_context: Optional[str] = None
    ) -> List[DialogueSegment]:
        """
        Generate a podcast script (sync wrapper for async method).
        """
        return asyncio.run(
            self.generate_script_async(
                facts=facts,
                topics=topics,
                target_duration_minutes=target_duration_minutes,
                episode_format=episode_format,
                language=language,
                audience_level=audience_level,
                cultural_context=cultural_context
            )
        )

    def _build_generation_prompt(
        self,
        facts: List[Dict[str, Any]],
        topics: List[str],
        personas: List[Persona],
        target_duration_minutes: int,
        episode_format: str,
        audience_level: str,
        cultural_context: Optional[str]
    ) -> str:
        """Build the prompt for script generation"""

        # Calculate target word count (150 words per minute)
        target_words = target_duration_minutes * 150

        # Format facts for the prompt
        facts_text = "\n".join([
            f"- [{f.get('id', 'unknown')}] {f.get('claim', f.get('text', ''))}"
            for f in facts
        ])

        # Format personas
        persona_text = "\n".join([
            f"- {p.name}: {p.style} style, expert in {p.expertise}"
            for p in personas
        ])

        prompt = f"""You are a podcast script writer creating a {episode_format} podcast episode.

## Episode Parameters
- Target Duration: {target_duration_minutes} minutes (~{target_words} words)
- Format: {episode_format}
- Audience Level: {audience_level}
- Language: Keep all dialogue natural and conversational

## Hosts
{persona_text}

## Topics to Cover
{', '.join(topics)}

## Facts to Include (cite by ID when using)
{facts_text}

## Cultural Context
{cultural_context or "General audience, no specific cultural adaptation needed."}

## Instructions
1. Create a natural, engaging dialogue between the hosts
2. Start with a brief introduction to the topic
3. Cover the key facts naturally in conversation
4. Include transitions between topics
5. End with a summary and call-to-action
6. When stating a fact, include the fact ID in brackets for citation tracking

## Required Format
Output the script in this exact format:
```
[INTRO]
{personas[0].name}: [introduction text]
{personas[1].name}: [response text]

[MAIN CONTENT]
{personas[0].name}: [dialogue] [fact_id if citing]
{personas[1].name}: [dialogue] [fact_id if citing]
...

[OUTRO]
{personas[0].name}: [closing text]
{personas[1].name}: [sign-off text]
```

Generate the complete script now:"""

        return prompt

    async def _call_llm_async(self, prompt: str) -> str:
        """
        Call LLM with retry logic (works with any provider).

        The model-agnostic interface handles provider-specific details.
        """
        import time

        system_prompt = """You are a podcast script writer.
Write natural, engaging dialogue between hosts.
Always include fact citations when stating facts.
Follow the exact format specified in the prompt."""

        for attempt in range(self.max_retries):
            try:
                response = await self._client.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.7,
                    max_tokens=4096
                )

                # Log usage for cost tracking
                print(f"[Generator] {response.provider}/{response.model}: "
                      f"{response.input_tokens}in/{response.output_tokens}out "
                      f"${response.estimated_cost:.4f} {response.latency_ms}ms")

                return response.content

            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"[Generator] Retry {attempt + 1} after {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    raise RuntimeError(f"Failed to generate script: {e}")

    def _call_claude(self, prompt: str) -> str:
        """Legacy sync method - redirects to async"""
        return asyncio.run(
            self._call_llm_async(prompt)
        )

    def _parse_script_response(
        self,
        response: str,
        personas: List[Persona]
    ) -> List[DialogueSegment]:
        """Parse Claude's response into DialogueSegments"""
        import re

        segments = []
        timestamp = 0

        # Get persona names for matching
        persona_names = [p.name for p in personas]

        # Split response into lines
        lines = response.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Skip section markers
            if line.startswith('[') and line.endswith(']'):
                continue

            # Try to parse as dialogue
            for persona in personas:
                if line.startswith(f"{persona.name}:"):
                    text = line[len(persona.name) + 1:].strip()

                    # Extract fact citations
                    fact_ids = re.findall(r'\[([a-zA-Z0-9_]+)\]', text)

                    # Remove citations from displayed text
                    clean_text = re.sub(r'\s*\[[a-zA-Z0-9_]+\]\s*', ' ', text).strip()

                    segments.append(DialogueSegment(
                        speaker=persona.name,
                        text=clean_text,
                        timestamp=timestamp,
                        fact_ids=fact_ids,
                        emotion="neutral",
                        verified=False
                    ))
                    timestamp += 1
                    break

        return segments

    async def revise_script_async(
        self,
        segments: List[DialogueSegment],
        feedback: str,
        issues: List[str]
    ) -> List[DialogueSegment]:
        """
        Revise a script based on verification feedback (async version).

        Args:
            segments: Current script segments
            feedback: Summary of issues
            issues: List of specific issues

        Returns:
            Revised list of DialogueSegments
        """
        self._ensure_client()

        # Format current script
        current_script = "\n".join([
            f"{seg.speaker}: {seg.text}"
            for seg in segments
        ])

        prompt = f"""You are revising a podcast script based on quality feedback.

## Current Script
{current_script}

## Issues to Fix
{feedback}

Specific issues:
{chr(10).join(f'- {issue}' for issue in issues)}

## Instructions
1. Fix each issue while maintaining natural dialogue
2. Keep the same format and speakers
3. Preserve the overall structure
4. Output the complete revised script

Revised script:"""

        response = await self._call_llm_async(prompt)

        # Get personas from current segments
        speaker_names = list(set(seg.speaker for seg in segments))
        personas = [
            Persona(name=name, style="", expertise="", voice_id="", language="english")
            for name in speaker_names
        ]

        return self._parse_script_response(response, personas)

    def revise_script(
        self,
        segments: List[DialogueSegment],
        feedback: str,
        issues: List[str]
    ) -> List[DialogueSegment]:
        """Revise script (sync wrapper)"""
        return asyncio.run(
            self.revise_script_async(segments, feedback, issues)
        )


def generator_node(state: PodcastState) -> Dict[str, Any]:
    """
    LangGraph node function for the Script Generator.

    This is the function called by LangGraph during workflow execution.

    Respects LLM_PROVIDER environment variable:
    - anthropic: Claude (best quality, expensive)
    - together: Qwen on Together.ai (good quality, cheap)
    - groq: Llama on Groq (fast)
    - ollama: Local models (free)
    """
    print(f"[Generator] Creating script for {state['target_duration_minutes']} min episode...")

    # Get facts from state (would come from Knowledge Graph)
    facts = [
        {"id": fact_id, "claim": f"Fact from {fact_id}"}
        for fact_id in state.get('fact_entity_ids', [])
    ]

    # Get topics
    topics = [
        f"Topic {topic_id}"
        for topic_id in state.get('topic_entity_ids', [])
    ]

    # If no facts/topics, use placeholder
    if not facts:
        facts = [
            {"id": "fact_001", "claim": "This is the main point about the topic"},
            {"id": "fact_002", "claim": "Here's an interesting supporting detail"},
            {"id": "fact_003", "claim": "And here's the conclusion"}
        ]

    if not topics:
        topics = [state.get('user_request', 'General topic')[:50]]

    # Determine which provider to use
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    has_any_key = any([
        os.environ.get("ANTHROPIC_API_KEY"),
        os.environ.get("TOGETHER_API_KEY"),
        os.environ.get("GROQ_API_KEY"),
        os.environ.get("OPENAI_API_KEY"),
    ])

    try:
        # Check if we have any API key
        if not has_any_key and provider != "ollama":
            # Return placeholder segments if no API key
            print("[Generator] No API key - using placeholder segments")
            print("[Generator] Set one of: ANTHROPIC_API_KEY, TOGETHER_API_KEY, GROQ_API_KEY")
            segments = _create_placeholder_segments(topics[0])
        else:
            # Get LLM config based on provider
            if provider == "together":
                llm_config = LLMConfig.cheap()
                print("[Generator] Using Together.ai (Qwen) - cheap mode")
            elif provider == "groq":
                llm_config = LLMConfig.fast()
                print("[Generator] Using Groq (Llama) - fast mode")
            elif provider == "ollama":
                llm_config = LLMConfig.local()
                print("[Generator] Using Ollama - local mode")
            else:
                llm_config = LLMConfig.quality()
                print("[Generator] Using Claude - quality mode")

            # Generate real script
            generator = ScriptGenerator(llm_config=llm_config)
            segments = generator.generate_script(
                facts=facts,
                topics=topics,
                target_duration_minutes=state['target_duration_minutes'],
                episode_format=state['episode_format'],
                language=state['target_language'],
                audience_level=state['audience_level']
            )

        # Create handoff
        handoff = LightweightHandoff(
            summary=f"Generated {len(segments)} dialogue segments",
            confidence=0.8,
            completeness=0.95,
            relevant_entities=[seg.speaker for seg in segments],
            known_gaps=[],
            flags=["needs_fact_check", "needs_flow_check"],
            requires_from_next=["verify_facts", "check_flow", "check_length"],
            full_context_ref="state.script_segments",
            source_agent="generator"
        )

        return {
            "current_agent": "verifier",
            "script_segments": segments,
            "handoffs": [handoff]
        }

    except Exception as e:
        print(f"[Generator] Error: {e}")
        return {
            "current_agent": "verifier",
            "processing_status": ProcessingStatus.FAILED,
            "error_message": str(e),
            "handoffs": [LightweightHandoff(
                summary=f"Script generation failed: {e}",
                confidence=0.0,
                completeness=0.0,
                relevant_entities=[],
                known_gaps=["script_generation_failed"],
                flags=["error"],
                requires_from_next=["handle_error"],
                full_context_ref="",
                source_agent="generator"
            )]
        }


def _create_placeholder_segments(topic: str) -> List[DialogueSegment]:
    """Create placeholder segments when API is not available"""
    return [
        DialogueSegment(
            speaker="Priya",
            text=f"Welcome to AI Builders Podcast! Today we're exploring {topic}.",
            timestamp=0,
            fact_ids=[]
        ),
        DialogueSegment(
            speaker="Arjun",
            text="That's right, Priya. This is a fascinating area with lots of recent developments.",
            timestamp=1,
            fact_ids=["fact_001"]
        ),
        DialogueSegment(
            speaker="Priya",
            text="Let's dive into the key points. What makes this topic so important right now?",
            timestamp=2,
            fact_ids=[]
        ),
        DialogueSegment(
            speaker="Arjun",
            text="Great question. There are several factors driving interest in this area.",
            timestamp=3,
            fact_ids=["fact_002"]
        ),
        DialogueSegment(
            speaker="Priya",
            text="That's really insightful. Any final thoughts for our listeners?",
            timestamp=4,
            fact_ids=[]
        ),
        DialogueSegment(
            speaker="Arjun",
            text="I'd encourage everyone to explore this further. It's an exciting time in this field.",
            timestamp=5,
            fact_ids=["fact_003"]
        ),
        DialogueSegment(
            speaker="Priya",
            text="Thanks for listening to AI Builders. See you next time!",
            timestamp=6,
            fact_ids=[]
        )
    ]

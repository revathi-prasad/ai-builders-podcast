"""
LangGraph Multi-Agent Workflow

This module defines the main workflow that orchestrates all agents.

LangGraph Key Concepts:
1. StateGraph: The workflow definition - a graph of nodes and edges
2. Nodes: Functions that process state (our agents)
3. Edges: Connections between nodes (can be conditional)
4. Checkpointing: Save/restore state for long-running workflows
5. Human-in-the-loop: Pause for human input when needed

Our Architecture:
- Hierarchical: Podcast Director controls the flow
- Sequential: Input → Research → Script → Verify → Output
- Collaborative: Verification agents can debate

Flow:
    [User Input]
         │
         ▼
    ┌─────────────┐
    │   Router    │ ── Classify input modalities
    └─────────────┘
         │
         ▼
    ┌─────────────┐
    │  Gatherer   │ ── Process inputs → Knowledge Graph
    └─────────────┘
         │
         ▼
    ┌─────────────┐
    │  Generator  │ ── Create script from graph
    └─────────────┘
         │
         ▼
    ┌─────────────┐
    │  Verifier   │ ── Check quality, fact-check
    └─────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  [Accept]  [Revise] ──→ Back to Generator
    │
    ▼
    ┌─────────────┐
    │ Synthesizer │ ── Generate audio
    └─────────────┘
         │
         ▼
    [Final Output]
"""

from typing import Literal, Dict, Any, Optional, List
from datetime import datetime
import logging
import json
import asyncio

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Our modules
from src.models.state import (
    PodcastState,
    ProcessingStatus,
    LightweightHandoff,
    VerificationResult,
    DialogueSegment,
    create_initial_state
)

# Import our actual agents
from src.agents.router import RouterAgent, ProcessingPath
from src.agents.generator import ScriptGenerator
from src.agents.synthesizer import AudioSynthesisAgent, VibeVoiceSynthesizer, DialogueSegment as SynthSegment

# Import tools
from src.tools.pdf_processor import PDFProcessor
from src.tools.audio_processor import AudioProcessor
from src.tools.url_processor import URLProcessor
from src.tools.text_processor import TextProcessor as TopicProcessor
from src.tools.web_search import WebSearchTool

# Import verification
from src.verification.fm_monitors import run_all_monitors, calculate_fm_reward
from src.verification.quality_checkers import run_all_checkers, aggregate_quality_score, should_revise

# Import Knowledge Graph
from src.graph.manager import KnowledgeGraphManager

# Import LLM client
from src.llm import get_llm_client

logger = logging.getLogger(__name__)


# ============================================================================
# KNOWLEDGE GRAPH SINGLETON
# ============================================================================

_kg_manager: Optional[KnowledgeGraphManager] = None


def get_kg_manager() -> KnowledgeGraphManager:
    """Get or create the Knowledge Graph manager singleton."""
    global _kg_manager
    if _kg_manager is None:
        _kg_manager = KnowledgeGraphManager()
        _kg_manager.initialize()
        logger.info("[KG] Knowledge Graph initialized")
    return _kg_manager


# ============================================================================
# LLM FACT EXTRACTION HELPER
# ============================================================================

async def _extract_facts_with_llm(text: str, topics: List[str]) -> List[Dict[str, Any]]:
    """
    Use LLM to extract structured facts from text.

    Returns list of dicts with keys: claim, confidence, topic
    Falls back to paragraph splitting if LLM call fails.
    """
    if not text.strip():
        return []

    # Truncate very long text to avoid token limits
    max_chars = 8000
    truncated = text[:max_chars] if len(text) > max_chars else text

    prompt = f"""Extract key facts from the following text. Return a JSON array of objects.
Each object should have:
- "claim": a single factual statement (one sentence)
- "confidence": how confident you are this is accurate (0.0 to 1.0)
- "topic": which topic this fact relates to (pick from: {', '.join(topics) if topics else 'general'})

Extract 5-15 facts. Focus on specific, verifiable claims rather than opinions.

Text:
{truncated}

Return ONLY valid JSON array, no other text:"""

    try:
        client = get_llm_client()
        response = await client.generate(
            prompt=prompt,
            temperature=0.1,
            max_tokens=2000
        )

        # Parse JSON from response
        content = response.content.strip()
        # Handle markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        facts = json.loads(content)
        if isinstance(facts, list):
            return facts

    except Exception as e:
        logger.warning(f"[KG] LLM fact extraction failed: {e}, falling back to paragraph split")

    # Fallback: split text into paragraph-level "facts"
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip() and len(p.strip()) > 30]
    return [
        {"claim": p[:200], "confidence": 0.5, "topic": topics[0] if topics else "general"}
        for p in paragraphs[:10]
    ]


# ============================================================================
# AGENT NODE FUNCTIONS
# ============================================================================

def router_node(state: PodcastState) -> Dict[str, Any]:
    """
    Router Agent: Classify and route input content.

    This is the entry point. It:
    1. Analyzes user request to understand intent
    2. Classifies each input by modality (doc, audio, URL, etc.)
    3. Flags copyright concerns
    4. Sets up processing plan

    Returns partial state update.
    """
    logger.info(f"[Router] Processing request: {state['user_request'][:100]}...")

    # Use real router agent
    router = RouterAgent(use_llm=False)  # Use heuristics for now

    # Convert input contents to expected format
    contents = [
        {"type": item.content_type.value, "source": item.source}
        for item in state['input_contents']
    ]

    decision = router.route(
        user_request=state['user_request'],
        contents=contents,
        target_language=state['target_language'],
        target_duration=state['target_duration_minutes']
    )

    # Create handoff for next agent
    handoff = LightweightHandoff(
        summary=f"Routed {len(state['input_contents'])} inputs via {decision.primary_path.value}",
        confidence=0.9,
        completeness=1.0,
        relevant_entities=decision.topics_identified,
        known_gaps=[],
        flags=decision.warnings,
        requires_from_next=["extract_content", "identify_topics"],
        full_context_ref="state.input_contents",
        source_agent="router"
    )

    return {
        "current_agent": "gatherer",
        "processing_status": ProcessingStatus.IN_PROGRESS,
        "routing_decision": decision,
        "topics": decision.topics_identified,
        "handoffs": state['handoffs'] + [handoff]
    }


def gatherer_node(state: PodcastState) -> Dict[str, Any]:
    """
    Content Gatherer Agent: Process all inputs and populate Knowledge Graph.

    This agent:
    1. Processes each input based on its modality
    2. Extracts topics, facts, and relationships via LLM
    3. Stores everything in Knowledge Graph with provenance
    4. Passes entity references (not content) to next agent
    """
    logger.info(f"[Gatherer] Processing {len(state['input_contents'])} content items...")

    # Initialize processors
    pdf_processor = PDFProcessor()
    audio_processor = AudioProcessor()
    url_processor = URLProcessor()
    topic_processor = TopicProcessor()

    # Get Knowledge Graph
    kg = get_kg_manager()

    # Process each input
    extracted_texts = []
    source_ids = []

    for i, item in enumerate(state['input_contents']):
        try:
            content_type = item.content_type.value
            source_type = content_type
            source_title = item.source[:80]

            if content_type == "document":
                result = pdf_processor.process(item.source)
                extracted_texts.append(result.text)
                logger.info(f"  Extracted {len(result.text)} chars from document")

            elif content_type == "audio":
                result = audio_processor.transcribe(item.source)
                extracted_texts.append(result.text)
                logger.info(f"  Transcribed {result.duration_seconds:.1f}s of audio")

            elif content_type == "url":
                result = url_processor.process(item.source)
                extracted_texts.append(result.text)
                logger.info(f"  Extracted {len(result.text)} chars from URL")

            elif content_type == "topic":
                topic_info = topic_processor.process_topic(item.source)
                extracted_texts.append(item.source)
                source_type = "user_input"
                logger.info(f"  Processed topic: {item.source[:50]}...")

                # Optionally enrich with web search results
                web_search = WebSearchTool()
                if web_search.available:
                    try:
                        search_results = asyncio.run(
                            web_search.search(item.source, num_results=5)
                        )
                        for sr in search_results:
                            extracted_texts.append(
                                f"{sr.get('title', '')}: {sr.get('snippet', '')}"
                            )
                            # Register each search result as a source in KG
                            web_sid = kg.add_source(
                                source_type="url",
                                url=sr.get("url", ""),
                                title=sr.get("title", ""),
                                reliability_score=0.6
                            )
                            source_ids.append(web_sid)
                        logger.info(f"  [WebSearch] Added {len(search_results)} search results")
                    except Exception as e:
                        logger.warning(f"  [WebSearch] Failed: {e}")

            else:
                extracted_texts.append(item.source)
                source_type = "user_input"
                logger.info(f"  Using raw text input")

            # Register source in KG
            sid = kg.add_source(
                source_type=source_type,
                url=item.source if content_type in ("url", "document", "audio") else "",
                title=source_title,
                reliability_score=0.7
            )
            source_ids.append(sid)

        except Exception as e:
            logger.warning(f"  Failed to process {item.source}: {e}")
            # Still register a low-reliability source
            sid = kg.add_source(
                source_type="user_input",
                title=f"Failed: {item.source[:50]}",
                reliability_score=0.2
            )
            source_ids.append(sid)

    combined_text = "\n\n".join(extracted_texts)

    # Extract topics and register in KG
    raw_topics = state.get('topics', [state['user_request']])
    topic_ids = []
    for topic_name in raw_topics:
        tid = kg.add_topic(
            name=topic_name,
            description=f"Topic from user request: {topic_name}",
            importance_score=0.8
        )
        topic_ids.append(tid)
        logger.info(f"  [KG] Added topic: {topic_name} → {tid}")

    # Use LLM to extract structured facts, then store in KG
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                raw_facts = pool.submit(
                    asyncio.run,
                    _extract_facts_with_llm(combined_text, raw_topics)
                ).result()
        else:
            raw_facts = loop.run_until_complete(
                _extract_facts_with_llm(combined_text, raw_topics)
            )
    except RuntimeError:
        raw_facts = asyncio.run(
            _extract_facts_with_llm(combined_text, raw_topics)
        )

    fact_ids = []
    for fact_data in raw_facts:
        fid = kg.add_fact(
            claim=fact_data.get("claim", ""),
            confidence=fact_data.get("confidence", 0.5),
            verified=False
        )
        fact_ids.append(fid)

        # Link fact to its topic
        fact_topic = fact_data.get("topic", "")
        for i, topic_name in enumerate(raw_topics):
            if fact_topic.lower() in topic_name.lower() or topic_name.lower() in fact_topic.lower():
                kg.link_fact_to_topic(fid, topic_ids[i], relevance=0.8)
                break
        else:
            # Link to first topic if no match
            if topic_ids:
                kg.link_fact_to_topic(fid, topic_ids[0], relevance=0.5)

        # Link fact to all sources (since we combined text)
        for sid in source_ids:
            kg.link_fact_to_source(fid, sid)

    logger.info(f"  [KG] Stored {len(fact_ids)} facts, {len(topic_ids)} topics, {len(source_ids)} sources")

    # Create handoff
    handoff = LightweightHandoff(
        summary=f"Extracted {len(topic_ids)} topics, {len(fact_ids)} facts from {len(extracted_texts)} inputs (KG populated)",
        confidence=0.85,
        completeness=0.9 if extracted_texts else 0.5,
        relevant_entities=topic_ids + fact_ids,
        known_gaps=["detailed_analysis"] if len(extracted_texts) == 0 else [],
        flags=["needs_fact_check"] if len(fact_ids) > 5 else [],
        requires_from_next=["generate_script", "maintain_flow"],
        full_context_ref="state.extracted_content",
        source_agent="gatherer"
    )

    return {
        "current_agent": "generator",
        "topic_entity_ids": topic_ids,
        "fact_entity_ids": fact_ids,
        "source_entity_ids": source_ids,
        "extracted_content": combined_text,
        "handoffs": state['handoffs'] + [handoff]
    }


def generator_node(state: PodcastState) -> Dict[str, Any]:
    """
    Script Generator Agent: Create the podcast script.

    This agent:
    1. Queries Knowledge Graph for structured facts with provenance
    2. Structures content into dialogue format
    3. Applies cultural adaptation
    4. Creates DialogueSegments with real fact citations
    """
    logger.info(f"[Generator] Creating script for {state['target_duration_minutes']} min episode...")

    # Check if this is a revision
    is_revision = any(
        h.source_agent == "verifier" and "needs_revision" in h.flags
        for h in state['handoffs']
    )

    # Use real script generator
    generator = ScriptGenerator()

    # Get topics and fact IDs from state
    topics = state.get('topics', [state['user_request']])
    fact_ids = state.get('fact_entity_ids', [])
    content = state.get('extracted_content', '')

    # Query KG for structured facts (instead of raw text splitting)
    kg = get_kg_manager()
    structured_facts = []

    for topic_name in topics:
        try:
            kg_facts = kg.get_facts_about_topic(topic_name)
            for row in kg_facts:
                structured_facts.append({
                    "id": row.get("f.id", "unknown"),
                    "claim": row.get("f.claim", ""),
                    "confidence": row.get("f.confidence", 0.5),
                    "verified": row.get("f.verified", False)
                })
        except Exception as e:
            logger.warning(f"  [KG] Query failed for topic '{topic_name}': {e}")

    # Fallback: if KG returned nothing, use extracted_content split into inline facts
    if not structured_facts and content:
        logger.info("  [KG] No facts from KG, falling back to inline text facts")
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        structured_facts = [
            {"id": f"inline_{i}", "claim": p[:200], "confidence": 0.5}
            for i, p in enumerate(paragraphs[:15])
        ]

    logger.info(f"  Using {len(structured_facts)} facts for script generation")

    try:
        if is_revision and state.get('script_segments'):
            # Revision mode - improve existing script
            issues = []
            for result in state.get('verification_results', []):
                issues.extend(result.issues)

            segments = generator.revise_script(
                segments=state['script_segments'],
                feedback="Improve based on verification feedback",
                issues=issues
            )
            logger.info(f"  Revised {len(segments)} segments")
        else:
            # New generation — pass structured facts (dicts with id + claim)
            segments = generator.generate_script(
                facts=structured_facts,
                topics=topics,
                target_duration_minutes=state['target_duration_minutes'],
                episode_format=state['episode_format'],
                language=state['target_language'],
                audience_level=state.get('audience_level', 'intermediate'),
                cultural_context=state.get('cultural_context')
            )
            logger.info(f"  Generated {len(segments)} new segments")

        # Convert to state DialogueSegment format
        state_segments = [
            DialogueSegment(
                speaker=seg.speaker,
                text=seg.text,
                timestamp=i,
                fact_ids=seg.fact_ids
            )
            for i, seg in enumerate(segments)
        ]

    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        # Fallback to placeholder
        state_segments = [
            DialogueSegment(
                speaker="Host",
                text=f"Welcome! Today we're discussing {topics[0] if topics else 'an interesting topic'}.",
                timestamp=0,
                fact_ids=[]
            ),
            DialogueSegment(
                speaker="Expert",
                text="That's right. Let me share some insights on this subject.",
                timestamp=1,
                fact_ids=fact_ids[:1] if fact_ids else []
            ),
        ]

    handoff = LightweightHandoff(
        summary=f"Generated {len(state_segments)} dialogue segments from {len(structured_facts)} KG facts",
        confidence=0.8,
        completeness=0.95,
        relevant_entities=list(set(s.speaker for s in state_segments)),
        known_gaps=[],
        flags=["needs_fact_check", "needs_flow_check"],
        requires_from_next=["verify_facts", "check_flow", "check_length"],
        full_context_ref="state.script_segments",
        source_agent="generator"
    )

    return {
        "current_agent": "verifier",
        "script_segments": state_segments,
        "handoffs": state['handoffs'] + [handoff]
    }


def verifier_node(state: PodcastState) -> Dict[str, Any]:
    """
    Quality Verifier Agent: Check script quality.

    This agent runs multiple checks:
    1. Fact Checker: Are claims supported by sources?
    2. Flow Checker: Is the conversation natural?
    3. Format Checker: Does it meet length/format requirements?
    4. Cultural Checker: Is it appropriate for target culture?

    Also generates FM monitor signals for RL training.
    """
    logger.info(f"[Verifier] Checking {len(state['script_segments'])} segments...")

    # Run quality checkers on script segments
    segments_data = [
        {
            "speaker": seg.speaker,
            "text": seg.text,
            "fact_ids": seg.fact_ids
        }
        for seg in state['script_segments']
    ]

    quality_results = run_all_checkers(segments_data, state)

    # Convert to state VerificationResult format
    results = [
        VerificationResult(
            checker_name=r.checker_name,
            passed=r.passed,
            score=r.score,
            issues=r.issues,
            suggestions=r.suggestions
        )
        for r in quality_results
    ]

    # Calculate overall score
    overall_score = aggregate_quality_score(quality_results)

    # Run FM monitors on handoffs for RL signals
    current_handoff = state['handoffs'][-1] if state['handoffs'] else None
    previous_handoffs = state['handoffs'][:-1] if len(state['handoffs']) > 1 else []

    if current_handoff:
        fm_results = run_all_monitors(current_handoff, previous_handoffs, state)
        fm_reward = calculate_fm_reward(fm_results)

        fm_signals = [
            {
                "monitor": r.monitor_name,
                "signal": r.reward_signal,
                "triggered": r.triggered,
                "details": r.explanation
            }
            for r in fm_results
        ]
    else:
        fm_reward = 0.0
        fm_signals = []

    # Determine if revision is needed
    needs_revision = should_revise(quality_results)

    # Count existing revisions to prevent infinite loops
    revision_count = sum(
        1 for h in state['handoffs']
        if h.source_agent == "verifier" and "needs_revision" in h.flags
    )
    max_revisions = 3

    if needs_revision and revision_count >= max_revisions:
        logger.warning(f"Max revisions ({max_revisions}) reached, proceeding to synthesis")
        needs_revision = False

    handoff = LightweightHandoff(
        summary=f"Verification complete. Score: {overall_score:.2f}, FM Reward: {fm_reward:.2f}",
        confidence=overall_score,
        completeness=1.0,
        relevant_entities=[],
        known_gaps=[],
        flags=["needs_revision"] if needs_revision else ["ready_for_synthesis"],
        requires_from_next=["revise_script"] if needs_revision else ["synthesize_audio"],
        full_context_ref="state.verification_results",
        source_agent="verifier"
    )

    return {
        "current_agent": "generator" if needs_revision else "synthesizer",
        "verification_results": results,
        "overall_quality_score": overall_score,
        "fm_reward": fm_reward,
        "fm_monitor_signals": fm_signals,
        "handoffs": state['handoffs'] + [handoff]
    }


def synthesizer_node(state: PodcastState) -> Dict[str, Any]:
    """
    Audio Synthesizer Agent: Generate the final audio.

    This agent:
    1. Formats the final script
    2. Calls VibeVoice (or gTTS fallback) for TTS
    3. Mixes audio with intro/outro music
    4. Saves the final file
    """
    logger.info(f"[Synthesizer] Generating audio for {len(state['script_segments'])} segments...")

    # Format final script
    final_script = "\n\n".join([
        f"{seg.speaker}: {seg.text}"
        for seg in state['script_segments']
    ])

    # Convert segments to synthesizer format
    synth_segments = [
        SynthSegment(
            speaker=seg.speaker,
            text=seg.text,
            pace=1.0
        )
        for seg in state['script_segments']
    ]

    # Use real synthesizer
    try:
        agent = AudioSynthesisAgent()
        result = agent.process({
            "script_segments": [
                {"speaker": seg.speaker, "text": seg.text}
                for seg in state['script_segments']
            ],
            "voice_config": state.get('voice_config', {}),
            "trace_id": state['trace_id']
        })

        audio_path = result.get('audio_path')
        audio_duration = result.get('audio_duration', 0)
        synthesis_metadata = result.get('synthesis_metadata', {})

        if result.get('error'):
            logger.warning(f"Synthesis had issues: {result['error']}")

    except Exception as e:
        logger.error(f"Audio synthesis failed: {e}")
        # Fallback - no audio but still complete
        audio_path = None
        audio_duration = 0
        synthesis_metadata = {"error": str(e), "note": "Audio synthesis failed, script only"}

    return {
        "current_agent": "complete",
        "processing_status": ProcessingStatus.COMPLETED,
        "final_script": final_script,
        "audio_file_path": audio_path,
        "audio_duration_seconds": audio_duration,
        "synthesis_metadata": synthesis_metadata
    }


# ============================================================================
# CONDITIONAL EDGES
# ============================================================================

def should_revise_or_synthesize(state: PodcastState) -> Literal["synthesizer", "generator"]:
    """
    Decide whether to proceed to synthesis or go back for revision.

    This is a conditional edge in the graph.
    """
    if state['overall_quality_score'] >= 0.7:
        return "synthesizer"
    else:
        # Check revision count to prevent infinite loops
        revision_count = sum(
            1 for h in state['handoffs']
            if h.source_agent == "verifier" and "needs_revision" in h.flags
        )
        if revision_count >= 3:
            print("[Warning] Max revisions reached, proceeding anyway")
            return "synthesizer"
        return "generator"


# ============================================================================
# BUILD THE GRAPH
# ============================================================================

def create_podcast_graph() -> StateGraph:
    """
    Create the LangGraph workflow for podcast generation.

    Returns a compiled StateGraph ready for execution.
    """
    # Create the graph with our state type
    workflow = StateGraph(PodcastState)

    # Add nodes (agents)
    workflow.add_node("router", router_node)
    workflow.add_node("gatherer", gatherer_node)
    workflow.add_node("generator", generator_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("synthesizer", synthesizer_node)

    # Add edges (flow)
    workflow.set_entry_point("router")

    # Linear flow from router → gatherer → generator
    workflow.add_edge("router", "gatherer")
    workflow.add_edge("gatherer", "generator")
    workflow.add_edge("generator", "verifier")

    # Conditional edge from verifier
    workflow.add_conditional_edges(
        "verifier",
        should_revise_or_synthesize,
        {
            "synthesizer": "synthesizer",
            "generator": "generator"  # Loop back for revision
        }
    )

    # Synthesizer → END
    workflow.add_edge("synthesizer", END)

    return workflow


def compile_graph(checkpointer=None):
    """
    Compile the graph for execution.

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled graph ready to invoke
    """
    workflow = create_podcast_graph()

    if checkpointer is None:
        checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer)


# ============================================================================
# EXECUTION HELPERS
# ============================================================================

async def generate_podcast(
    user_request: str,
    input_contents: list,
    target_language: str = "english",
    target_duration_minutes: int = 10,
    episode_format: str = "conversation"
) -> PodcastState:
    """
    High-level function to generate a podcast.

    This is the main entry point for the API.
    """
    # Create initial state
    from src.models.state import ContentItem, ContentType

    # Convert raw inputs to ContentItems
    content_items = []
    for item in input_contents:
        content_items.append(ContentItem(
            content_type=ContentType(item.get("type", "topic")),
            source=item.get("source", "")
        ))

    initial_state = create_initial_state(
        user_request=user_request,
        input_contents=content_items,
        target_language=target_language,
        target_duration_minutes=target_duration_minutes,
        episode_format=episode_format
    )

    # Compile and run the graph
    graph = compile_graph()

    # Run the workflow
    config = {"configurable": {"thread_id": initial_state["trace_id"]}}
    final_state = await graph.ainvoke(initial_state, config)

    return final_state


# For synchronous execution
def generate_podcast_sync(
    user_request: str,
    input_contents: list,
    target_language: str = "english",
    target_duration_minutes: int = 10,
    episode_format: str = "conversation"
) -> PodcastState:
    """Synchronous version of generate_podcast"""
    import asyncio
    return asyncio.run(generate_podcast(
        user_request=user_request,
        input_contents=input_contents,
        target_language=target_language,
        target_duration_minutes=target_duration_minutes,
        episode_format=episode_format
    ))

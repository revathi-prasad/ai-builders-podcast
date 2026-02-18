"""
LangGraph Workflow Runner

This module handles the actual execution of the LangGraph workflow
from the API. It bridges the FastAPI endpoints with the multi-agent system.
"""

import asyncio
from typing import Dict, Any, Callable, Optional
from datetime import datetime

from src.models.state import (
    PodcastState,
    ProcessingStatus,
    ContentItem,
    ContentType,
    LightweightHandoff,
    create_initial_state
)
from src.agents.graph import compile_graph
from src.verification.fm_monitors import run_all_monitors, calculate_fm_reward
from src.verification.quality_checkers import run_all_checkers, aggregate_quality_score


class WorkflowRunner:
    """
    Runs the LangGraph workflow with progress callbacks.

    This class wraps the LangGraph execution to provide:
    - Progress tracking
    - FM monitor integration
    - Error handling
    - Result formatting
    """

    def __init__(self):
        self.graph = compile_graph()

    async def run(
        self,
        request: Dict[str, Any],
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Run the podcast generation workflow.

        Args:
            request: Generation request from API
            progress_callback: Optional callback(progress: int, step: str)

        Returns:
            Dict with results or error
        """
        try:
            # Create initial state
            content_items = [
                ContentItem(
                    content_type=ContentType(c.get("type", "topic")),
                    source=c.get("source", "")
                )
                for c in request.get("contents", [])
            ]

            # If no contents but we have a user_request, use it as topic
            if not content_items and request.get("user_request"):
                content_items = [
                    ContentItem(
                        content_type=ContentType.TOPIC,
                        source=request["user_request"]
                    )
                ]

            initial_state = create_initial_state(
                user_request=request.get("user_request", ""),
                input_contents=content_items,
                target_language=request.get("target_language", "english"),
                target_duration_minutes=request.get("target_duration_minutes", 10),
                episode_format=request.get("episode_format", "conversation"),
                audience_level=request.get("audience_level", "intermediate")
            )

            if progress_callback:
                progress_callback(5, "Initialized workflow")

            # Run the graph
            config = {"configurable": {"thread_id": initial_state["trace_id"]}}

            # For now, run synchronously with progress updates
            # In production, use streaming for real-time updates
            final_state = await self._run_with_progress(
                initial_state,
                config,
                progress_callback
            )

            return self._format_result(final_state)

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "final_script": None,
                "audio_file_path": None,
                "quality_score": 0.0
            }

    async def _run_with_progress(
        self,
        initial_state: PodcastState,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[int, str], None]]
    ) -> PodcastState:
        """Run graph with real progress updates via streaming."""

        # Map node names to progress percentages
        agent_progress = {
            "router": (10, "Analyzing input"),
            "gatherer": (30, "Processing content"),
            "generator": (55, "Generating script"),
            "verifier": (75, "Verifying quality"),
            "synthesizer": (90, "Synthesizing audio"),
        }

        try:
            final_state = None

            # Use astream to get real node-completion events
            async for event in self.graph.astream(initial_state, config):
                # event is a dict with node name as key
                for node_name in event:
                    if node_name in agent_progress and progress_callback:
                        progress, step = agent_progress[node_name]
                        progress_callback(progress, step)
                    # Keep track of latest state
                    final_state = event[node_name] if isinstance(event[node_name], dict) else final_state

            if progress_callback:
                progress_callback(100, "Done")

            # astream yields partial state updates; get final state via ainvoke fallback
            # if streaming didn't produce a complete state
            if final_state is None:
                final_state = await self.graph.ainvoke(initial_state, config)

            return final_state

        except Exception as e:
            if progress_callback:
                progress_callback(0, f"Error: {e}")
            raise

    def _format_result(self, state: PodcastState) -> Dict[str, Any]:
        """Format the final state into API response"""

        # Run quality checks on final segments
        segments = state.get("script_segments", [])
        quality_results = run_all_checkers(segments, state)
        quality_score = aggregate_quality_score(quality_results)

        # Calculate FM reward from handoffs
        handoffs = state.get("handoffs", [])
        fm_reward = 0.0
        if len(handoffs) >= 2:
            for i, handoff in enumerate(handoffs[1:], 1):
                previous = handoffs[:i]
                fm_results = run_all_monitors(handoff, previous, state)
                fm_reward += calculate_fm_reward(fm_results)
            fm_reward /= len(handoffs) - 1

        # Format segments for response
        formatted_segments = [
            {
                "speaker": seg.speaker,
                "text": seg.text,
                "timestamp": seg.timestamp,
                "fact_ids": seg.fact_ids
            }
            for seg in segments
        ]

        return {
            "success": state.get("processing_status") == ProcessingStatus.COMPLETED,
            "final_script": state.get("final_script", ""),
            "audio_file_path": state.get("audio_file_path"),
            "quality_score": quality_score,
            "fm_reward": fm_reward,
            "duration_minutes": state.get("target_duration_minutes", 10),
            "segments": formatted_segments,
            "verification_results": [
                {
                    "checker": r.checker_name,
                    "passed": r.passed,
                    "score": r.score,
                    "issues": r.issues,
                    "suggestions": r.suggestions
                }
                for r in quality_results
            ],
            "metadata": {
                "trace_id": state.get("trace_id", ""),
                "language": state.get("target_language", "english"),
                "format": state.get("episode_format", "conversation"),
                "handoff_count": len(handoffs)
            }
        }


# Singleton runner instance
_runner: Optional[WorkflowRunner] = None


def get_runner() -> WorkflowRunner:
    """Get or create the workflow runner"""
    global _runner
    if _runner is None:
        _runner = WorkflowRunner()
    return _runner


async def run_generation_workflow(
    request: Dict[str, Any],
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> Dict[str, Any]:
    """
    Convenience function to run the workflow.

    This is what the API calls.
    """
    runner = get_runner()
    return await runner.run(request, progress_callback)

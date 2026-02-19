"""
Failure Mode Monitors (Layer 1)

Based on the MAST (Multi-Agent System failure Taxonomy) paper,
these monitors detect specific failure patterns in agent communication.

FM-2.1: Context Reset - Agent loses critical context during handoff
FM-2.3: Task Derailment - Agent drifts from assigned task
FM-2.4: Information Withholding - Agent fails to share relevant info
FM-2.6: Reasoning-Action Mismatch - Action doesn't match stated reasoning

These monitors run on every inter-agent message and generate dense
reward signals for RL training. They're designed to be fast (use small
local LLM like Qwen3 8B) since they run frequently.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.models.state import LightweightHandoff, PodcastState


class MonitorSignal(Enum):
    """Signal values from FM monitors"""
    PASS = 0       # No failure detected
    WARNING = -0.5  # Potential issue, not definitive
    FAILURE = -1    # Clear failure mode detected


@dataclass
class MonitorResult:
    """Result from a single FM monitor check"""
    monitor_name: str
    signal: MonitorSignal
    confidence: float  # How confident in the detection (0-1)
    details: str
    evidence: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "monitor": self.monitor_name,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "details": self.details,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat()
        }


class FMMonitor(ABC):
    """
    Base class for Failure Mode monitors.

    Each monitor checks for a specific failure pattern and returns
    a signal that can be used for RL reward shaping.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Monitor identifier (e.g., 'FM-2.1')"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """What this monitor checks for"""
        pass

    @abstractmethod
    def check(
        self,
        current_handoff: LightweightHandoff,
        previous_handoffs: List[LightweightHandoff],
        state: PodcastState
    ) -> MonitorResult:
        """
        Check for the failure mode.

        Args:
            current_handoff: The handoff being evaluated
            previous_handoffs: Previous handoffs for context
            state: Current workflow state

        Returns:
            MonitorResult with signal and details
        """
        pass


class ContextResetMonitor(FMMonitor):
    """
    FM-2.1: Context Reset Detection

    Detects when an agent loses critical context that was present
    in previous handoffs. This is one of the most common failure modes.

    Signs of context reset:
    - Key entities from previous handoffs not referenced
    - Known gaps not addressed
    - Confidence drops significantly without explanation
    """

    @property
    def name(self) -> str:
        return "FM-2.1"

    @property
    def description(self) -> str:
        return "Context Reset Detection"

    def check(
        self,
        current_handoff: LightweightHandoff,
        previous_handoffs: List[LightweightHandoff],
        state: PodcastState
    ) -> MonitorResult:

        if not previous_handoffs:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.PASS,
                confidence=1.0,
                details="No previous context to compare"
            )

        last_handoff = previous_handoffs[-1]
        evidence = []

        # Check 1: Are relevant entities preserved?
        last_entities = set(last_handoff.relevant_entities)
        current_entities = set(current_handoff.relevant_entities)
        missing_entities = last_entities - current_entities

        # Allow some entity reduction (natural progression), but flag if too many lost
        if len(missing_entities) > len(last_entities) * 0.5:
            evidence.append(
                f"Lost {len(missing_entities)}/{len(last_entities)} entities: "
                f"{list(missing_entities)[:5]}"
            )

        # Check 2: Were known gaps addressed or passed on?
        last_gaps = set(last_handoff.known_gaps)
        current_gaps = set(current_handoff.known_gaps)
        dropped_gaps = last_gaps - current_gaps

        # If gaps were dropped but not addressed, that's suspicious
        if dropped_gaps and "resolve_gaps" not in current_handoff.requires_from_next:
            evidence.append(f"Dropped gaps without resolution: {list(dropped_gaps)}")

        # Check 3: Unexplained confidence drop
        if current_handoff.confidence < last_handoff.confidence - 0.3:
            if "error" not in current_handoff.flags:
                evidence.append(
                    f"Confidence dropped {last_handoff.confidence:.2f} → "
                    f"{current_handoff.confidence:.2f} without error flag"
                )

        # Determine signal
        if len(evidence) >= 2:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.FAILURE,
                confidence=0.8,
                details="Multiple signs of context reset detected",
                evidence=evidence
            )
        elif len(evidence) == 1:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.WARNING,
                confidence=0.6,
                details="Possible context reset",
                evidence=evidence
            )
        else:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.PASS,
                confidence=0.9,
                details="Context preserved"
            )


class InfoWithholdingMonitor(FMMonitor):
    """
    FM-2.4: Information Withholding Detection

    Detects when an agent has relevant information but doesn't
    share it in the handoff. This can happen due to:
    - Token limits causing truncation
    - Agent deciding info isn't relevant (incorrectly)
    - Bugs in information extraction

    Signs of withholding:
    - High completeness claim but low entity count
    - Mentions "more details" without providing them
    - Known entities in state not referenced in handoff
    """

    @property
    def name(self) -> str:
        return "FM-2.4"

    @property
    def description(self) -> str:
        return "Information Withholding Detection"

    def check(
        self,
        current_handoff: LightweightHandoff,
        previous_handoffs: List[LightweightHandoff],
        state: PodcastState
    ) -> MonitorResult:

        evidence = []

        # Check 1: Completeness vs entity ratio
        if current_handoff.completeness > 0.8 and len(current_handoff.relevant_entities) < 2:
            evidence.append(
                f"Claims {current_handoff.completeness:.0%} complete but only "
                f"{len(current_handoff.relevant_entities)} entities"
            )

        # Check 2: State has entities not in handoff
        state_topics = set(state.get('topic_entity_ids', []))
        state_facts = set(state.get('fact_entity_ids', []))
        all_state_entities = state_topics | state_facts
        handoff_entities = set(current_handoff.relevant_entities)

        if all_state_entities and handoff_entities:
            unreferenced = all_state_entities - handoff_entities
            if len(unreferenced) > len(all_state_entities) * 0.7:
                evidence.append(
                    f"{len(unreferenced)} state entities not mentioned in handoff"
                )

        # Check 3: Summary too short for claimed completeness
        words_in_summary = len(current_handoff.summary.split())
        if current_handoff.completeness > 0.8 and words_in_summary < 20:
            evidence.append(
                f"Summary only {words_in_summary} words for {current_handoff.completeness:.0%} completeness"
            )

        # Determine signal
        if len(evidence) >= 2:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.FAILURE,
                confidence=0.75,
                details="Information likely withheld",
                evidence=evidence
            )
        elif len(evidence) == 1:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.WARNING,
                confidence=0.5,
                details="Possible information withholding",
                evidence=evidence
            )
        else:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.PASS,
                confidence=0.85,
                details="Information sharing appears complete"
            )


class TaskDerailmentMonitor(FMMonitor):
    """
    FM-2.3: Task Derailment Detection

    Detects when an agent drifts away from its assigned task.
    This can happen when:
    - Agent gets distracted by tangential information
    - Agent misunderstands its role
    - Prompt injection attempts

    Signs of derailment:
    - Output doesn't match requires_from_next expectations
    - New unrelated topics introduced
    - Agent role mismatch
    """

    @property
    def name(self) -> str:
        return "FM-2.3"

    @property
    def description(self) -> str:
        return "Task Derailment Detection"

    def check(
        self,
        current_handoff: LightweightHandoff,
        previous_handoffs: List[LightweightHandoff],
        state: PodcastState
    ) -> MonitorResult:

        evidence = []

        if not previous_handoffs:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.PASS,
                confidence=1.0,
                details="No previous task to compare"
            )

        last_handoff = previous_handoffs[-1]

        # Check 1: Did this agent do what was expected?
        expected_tasks = set(last_handoff.requires_from_next)
        if expected_tasks:
            # Check if any expected task is reflected in current work
            summary_lower = current_handoff.summary.lower()
            tasks_addressed = sum(
                1 for task in expected_tasks
                if any(word in summary_lower for word in task.lower().split('_'))
            )
            if tasks_addressed == 0:
                evidence.append(
                    f"Expected tasks {expected_tasks} not addressed in summary"
                )

        # Check 2: Agent role consistency
        expected_agents = {
            "router": ["gatherer"],
            "gatherer": ["generator"],
            "generator": ["verifier"],
            "verifier": ["synthesizer", "generator"]  # Can loop back
        }

        expected_next = expected_agents.get(last_handoff.source_agent, [])
        if expected_next and current_handoff.source_agent not in expected_next:
            evidence.append(
                f"Unexpected agent transition: {last_handoff.source_agent} → "
                f"{current_handoff.source_agent} (expected {expected_next})"
            )

        # Check 3: New unrelated flags
        suspicious_flags = {"off_topic", "unrelated", "tangent"}
        if any(flag in current_handoff.flags for flag in suspicious_flags):
            evidence.append("Self-reported off-topic flag detected")

        # Determine signal
        if len(evidence) >= 2:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.FAILURE,
                confidence=0.7,
                details="Task derailment detected",
                evidence=evidence
            )
        elif len(evidence) == 1:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.WARNING,
                confidence=0.5,
                details="Possible task drift",
                evidence=evidence
            )
        else:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.PASS,
                confidence=0.9,
                details="Task progression normal"
            )


class ReasoningActionMonitor(FMMonitor):
    """
    FM-2.6: Reasoning-Action Mismatch Detection

    Detects when an agent's stated reasoning doesn't match
    its actions. This is important for:
    - Detecting deceptive behavior
    - Finding bugs in decision logic
    - Identifying hallucinated confidence

    Signs of mismatch:
    - Claims success but reports errors
    - Low confidence but proceeds anyway
    - Contradictory flags
    """

    @property
    def name(self) -> str:
        return "FM-2.6"

    @property
    def description(self) -> str:
        return "Reasoning-Action Mismatch Detection"

    def check(
        self,
        current_handoff: LightweightHandoff,
        previous_handoffs: List[LightweightHandoff],
        state: PodcastState
    ) -> MonitorResult:

        evidence = []

        # Check 1: Confidence vs flags consistency
        if current_handoff.confidence > 0.8 and "error" in current_handoff.flags:
            evidence.append(
                f"High confidence ({current_handoff.confidence:.2f}) despite error flag"
            )

        if current_handoff.confidence < 0.5 and "ready_for_synthesis" in current_handoff.flags:
            evidence.append(
                f"Low confidence ({current_handoff.confidence:.2f}) but marked ready"
            )

        # Check 2: Completeness vs known gaps
        if current_handoff.completeness > 0.9 and len(current_handoff.known_gaps) > 3:
            evidence.append(
                f"Claims {current_handoff.completeness:.0%} complete but has "
                f"{len(current_handoff.known_gaps)} gaps"
            )

        # Check 3: Contradictory flags
        contradictory_pairs = [
            ("needs_revision", "ready_for_synthesis"),
            ("error", "completed"),
            ("needs_fact_check", "verified")
        ]
        flags_set = set(current_handoff.flags)
        for flag1, flag2 in contradictory_pairs:
            if flag1 in flags_set and flag2 in flags_set:
                evidence.append(f"Contradictory flags: {flag1} and {flag2}")

        # Check 4: Summary sentiment vs confidence
        negative_words = ["failed", "error", "unable", "couldn't", "problem"]
        positive_words = ["success", "completed", "done", "ready", "good"]

        summary_lower = current_handoff.summary.lower()
        has_negative = any(word in summary_lower for word in negative_words)
        has_positive = any(word in summary_lower for word in positive_words)

        if has_negative and current_handoff.confidence > 0.8:
            evidence.append("Negative summary language with high confidence")
        if has_positive and current_handoff.confidence < 0.4:
            evidence.append("Positive summary language with low confidence")

        # Determine signal
        if len(evidence) >= 2:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.FAILURE,
                confidence=0.8,
                details="Clear reasoning-action mismatch",
                evidence=evidence
            )
        elif len(evidence) == 1:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.WARNING,
                confidence=0.6,
                details="Possible reasoning inconsistency",
                evidence=evidence
            )
        else:
            return MonitorResult(
                monitor_name=self.name,
                signal=MonitorSignal.PASS,
                confidence=0.9,
                details="Reasoning-action alignment normal"
            )


# ============================================================================
# RUN ALL MONITORS
# ============================================================================

def run_all_monitors(
    current_handoff: LightweightHandoff,
    previous_handoffs: List[LightweightHandoff],
    state: PodcastState
) -> List[MonitorResult]:
    """
    Run all FM monitors on a handoff.

    Returns list of MonitorResults for RL reward shaping.
    """
    monitors = [
        ContextResetMonitor(),
        InfoWithholdingMonitor(),
        TaskDerailmentMonitor(),
        ReasoningActionMonitor()
    ]

    results = []
    for monitor in monitors:
        try:
            result = monitor.check(current_handoff, previous_handoffs, state)
            results.append(result)
        except Exception as e:
            # Don't let monitor failures break the pipeline
            results.append(MonitorResult(
                monitor_name=monitor.name,
                signal=MonitorSignal.PASS,
                confidence=0.0,
                details=f"Monitor error: {e}"
            ))

    return results


def calculate_fm_reward(results: List[MonitorResult]) -> float:
    """
    Calculate aggregate reward signal from FM monitor results.

    Returns a value between -1 (all failures) and 0 (no issues).
    """
    if not results:
        return 0.0

    total_signal = sum(r.signal.value * r.confidence for r in results)
    max_possible = len(results)  # All failures would be -1 * num_monitors

    return total_signal / max_possible  # Normalized

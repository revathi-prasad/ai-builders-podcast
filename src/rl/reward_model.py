"""
Reward Models for Podcast Generation

Multiple reward signals combined:
1. Explicit ratings (user-provided 1-5 stars)
2. Pairwise preferences (A vs B comparisons)
3. Implicit engagement (listen-through rate, replays, skips)
4. Quality metrics (factual accuracy, coherence, engagement)

Research Note:
The combination of explicit + implicit signals is novel in podcast domain.
Prior work (e.g., InstructGPT) focused primarily on explicit human ratings.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np


@dataclass
class RewardSignal:
    """A computed reward signal"""
    value: float              # Scalar reward in [0, 1]
    confidence: float = 1.0   # How confident is this signal
    source: str = "unknown"   # Where did this come from
    breakdown: Dict[str, float] = field(default_factory=dict)


class RewardModel(ABC):
    """
    Abstract base class for reward models.

    Reward models convert various feedback signals into scalar rewards
    that can be used for RL training.
    """

    @abstractmethod
    def compute_reward(
        self,
        prompt: str,
        generation: str,
        metadata: Dict[str, Any] = None
    ) -> RewardSignal:
        """
        Compute reward for a generation.

        Args:
            prompt: The input prompt/topic
            generation: The generated script/dialogue
            metadata: Additional context (user feedback, metrics, etc.)

        Returns:
            RewardSignal with value and metadata
        """
        pass

    @abstractmethod
    def train(self, examples: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Train/update the reward model.

        Args:
            examples: Training examples with (prompt, response, reward)

        Returns:
            Training metrics
        """
        pass


class EngagementRewardModel(RewardModel):
    """
    Reward model based on listener engagement signals.

    Combines:
    - Listen-through rate (primary signal)
    - Replay behavior (bonus)
    - Skip behavior (penalty)
    - Explicit ratings (when available)

    This is the novel contribution: using implicit listener behavior
    as reward signal for creative content generation.
    """

    def __init__(
        self,
        listen_weight: float = 0.4,
        replay_weight: float = 0.2,
        skip_weight: float = 0.1,
        explicit_weight: float = 0.3,
        quality_weight: float = 0.0,  # Reserved for quality metrics
    ):
        """
        Initialize the engagement reward model.

        Args:
            listen_weight: Weight for listen-through rate
            replay_weight: Weight for replay bonus
            skip_weight: Weight for skip penalty
            explicit_weight: Weight for explicit ratings
            quality_weight: Weight for automated quality metrics
        """
        self.weights = {
            "listen": listen_weight,
            "replay": replay_weight,
            "skip": skip_weight,
            "explicit": explicit_weight,
            "quality": quality_weight
        }

        # Normalize weights
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v/total for k, v in self.weights.items()}

        # Statistics for normalization
        self.stats = {
            "listen_mean": 0.6,
            "listen_std": 0.2,
            "replay_mean": 0.5,
            "skip_mean": 1.0,
            "explicit_mean": 3.5,
        }

    def compute_reward(
        self,
        prompt: str,
        generation: str,
        metadata: Dict[str, Any] = None
    ) -> RewardSignal:
        """
        Compute engagement-based reward.

        Expected metadata:
        - listen_through_rate: 0-1 (required)
        - replay_count: int
        - skip_count: int
        - explicit_rating: 1-5 (optional)
        """
        metadata = metadata or {}
        breakdown = {}

        # Listen-through rate (core signal)
        listen_rate = metadata.get("listen_through_rate", 0.5)
        listen_score = self._normalize(listen_rate, 0, 1)
        breakdown["listen"] = listen_score

        # Replay bonus
        replay_count = metadata.get("replay_count", 0)
        replay_score = min(replay_count / 3, 1.0)  # Cap at 3 replays
        breakdown["replay"] = replay_score

        # Skip penalty
        skip_count = metadata.get("skip_count", 0)
        skip_score = max(0, 1 - (skip_count / 5))  # Penalty per skip
        breakdown["skip"] = skip_score

        # Explicit rating (if available)
        explicit_rating = metadata.get("explicit_rating")
        if explicit_rating is not None:
            explicit_score = (explicit_rating - 1) / 4  # Normalize 1-5 to 0-1
            breakdown["explicit"] = explicit_score
        else:
            # No explicit rating - redistribute weight
            breakdown["explicit"] = None

        # Compute weighted average
        total_weight = 0
        weighted_sum = 0

        for signal, score in breakdown.items():
            if score is not None:
                weight = self.weights.get(signal, 0)
                weighted_sum += score * weight
                total_weight += weight

        if total_weight > 0:
            final_reward = weighted_sum / total_weight
        else:
            final_reward = 0.5

        # Confidence based on data availability
        confidence = sum(1 for v in breakdown.values() if v is not None) / len(breakdown)

        return RewardSignal(
            value=final_reward,
            confidence=confidence,
            source="engagement",
            breakdown={k: v for k, v in breakdown.items() if v is not None}
        )

    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize value to [0, 1]"""
        if max_val == min_val:
            return 0.5
        return max(0, min(1, (value - min_val) / (max_val - min_val)))

    def train(self, examples: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Update statistics from training examples.

        This model doesn't have learnable parameters, but we update
        normalization statistics.
        """
        if not examples:
            return {"status": "no_examples"}

        # Collect statistics
        listen_rates = [ex.get("listen_through_rate", 0.5) for ex in examples]
        replay_counts = [ex.get("replay_count", 0) for ex in examples]
        skip_counts = [ex.get("skip_count", 0) for ex in examples]
        explicit_ratings = [
            ex.get("explicit_rating")
            for ex in examples
            if ex.get("explicit_rating") is not None
        ]

        # Update stats
        if listen_rates:
            self.stats["listen_mean"] = np.mean(listen_rates)
            self.stats["listen_std"] = np.std(listen_rates) or 0.2

        if replay_counts:
            self.stats["replay_mean"] = np.mean(replay_counts)

        if skip_counts:
            self.stats["skip_mean"] = np.mean(skip_counts)

        if explicit_ratings:
            self.stats["explicit_mean"] = np.mean(explicit_ratings)

        return {
            "examples_processed": len(examples),
            "listen_mean": self.stats["listen_mean"],
            "explicit_count": len(explicit_ratings)
        }

    def save(self, path: str) -> None:
        """Save model state"""
        data = {
            "weights": self.weights,
            "stats": self.stats
        }
        Path(path).write_text(json.dumps(data, indent=2))

    def load(self, path: str) -> None:
        """Load model state"""
        data = json.loads(Path(path).read_text())
        self.weights = data["weights"]
        self.stats = data["stats"]


class QualityRewardModel(RewardModel):
    """
    Reward model based on automated quality metrics.

    Uses FM monitors and quality checkers to assess:
    - Factual accuracy
    - Dialogue coherence
    - Engagement potential
    - Safety/appropriateness

    This can run without human feedback, enabling larger-scale training.
    """

    def __init__(self, quality_checkers=None):
        """
        Initialize with quality checker modules.

        Args:
            quality_checkers: List of quality checker instances
        """
        self.quality_checkers = quality_checkers or []

    def compute_reward(
        self,
        prompt: str,
        generation: str,
        metadata: Dict[str, Any] = None
    ) -> RewardSignal:
        """
        Compute quality-based reward using automated checkers.
        """
        if not self.quality_checkers:
            # No checkers configured - return neutral
            return RewardSignal(
                value=0.5,
                confidence=0.0,
                source="quality_unconfigured"
            )

        breakdown = {}
        scores = []

        for checker in self.quality_checkers:
            try:
                result = checker.check(generation, prompt)
                score = result.get("score", 0.5)
                breakdown[checker.name] = score
                scores.append(score)
            except Exception as e:
                print(f"[QualityReward] Checker {checker.name} failed: {e}")

        if scores:
            final_reward = np.mean(scores)
        else:
            final_reward = 0.5

        return RewardSignal(
            value=final_reward,
            confidence=len(scores) / max(len(self.quality_checkers), 1),
            source="quality",
            breakdown=breakdown
        )

    def train(self, examples: List[Dict[str, Any]]) -> Dict[str, float]:
        """Quality model doesn't train - it uses fixed metrics"""
        return {"status": "quality_model_no_training"}


class CompositeRewardModel(RewardModel):
    """
    Combines multiple reward models with learned weights.

    This enables the waterfall feedback approach:
    1. Start with quality metrics (automated, cheap)
    2. Add explicit ratings (expensive, high signal)
    3. Incorporate implicit engagement (requires production use)
    """

    def __init__(
        self,
        models: List[Tuple[str, RewardModel, float]] = None
    ):
        """
        Initialize with component models.

        Args:
            models: List of (name, model, initial_weight) tuples
        """
        self.models = models or []

    def add_model(self, name: str, model: RewardModel, weight: float = 1.0) -> None:
        """Add a component reward model"""
        self.models.append((name, model, weight))

    def compute_reward(
        self,
        prompt: str,
        generation: str,
        metadata: Dict[str, Any] = None
    ) -> RewardSignal:
        """Compute weighted combination of all models"""
        signals = []
        breakdown = {}
        total_weight = 0

        for name, model, weight in self.models:
            try:
                signal = model.compute_reward(prompt, generation, metadata)
                signals.append((signal, weight * signal.confidence))
                breakdown[name] = signal.value
                total_weight += weight * signal.confidence
            except Exception as e:
                print(f"[CompositeReward] Model {name} failed: {e}")

        if total_weight > 0:
            weighted_sum = sum(s.value * w for s, w in signals)
            final_reward = weighted_sum / total_weight
        else:
            final_reward = 0.5

        avg_confidence = np.mean([s.confidence for s, _ in signals]) if signals else 0

        return RewardSignal(
            value=final_reward,
            confidence=avg_confidence,
            source="composite",
            breakdown=breakdown
        )

    def train(self, examples: List[Dict[str, Any]]) -> Dict[str, float]:
        """Train all component models"""
        results = {}
        for name, model, _ in self.models:
            try:
                model_results = model.train(examples)
                results[name] = model_results
            except Exception as e:
                results[name] = {"error": str(e)}
        return results

"""
Reinforcement Learning Training Pipeline

Research module for RL experiments on podcast generation:
- Reward modeling from feedback signals
- DPO (Direct Preference Optimization)
- GRPO (Group Relative Policy Optimization)
- Ablation studies across models

Key Research Questions:
- How do different feedback signals (explicit/pairwise/implicit) affect generation quality?
- Does RL improve creative podcast dialogue over vanilla fine-tuning?
- Which open-source models benefit most from RL fine-tuning?

Prior Work Context:
- DPO vs PPO: ICLR 2025 papers show DPO is simpler but PPO can be better with good reward models
- MAGRPO: Multi-agent collaboration via RL (we apply this to multi-speaker dialogues)
- Our novelty: Application to creative podcast domain with listener engagement as reward
"""

from .reward_model import RewardModel, EngagementRewardModel
from .trainer import (
    RLTrainer,
    DPOTrainer,
    GRPOTrainer,
    TrainingConfig,
    TrainingMetrics
)

__all__ = [
    "RewardModel",
    "EngagementRewardModel",
    "RLTrainer",
    "DPOTrainer",
    "GRPOTrainer",
    "TrainingConfig",
    "TrainingMetrics"
]

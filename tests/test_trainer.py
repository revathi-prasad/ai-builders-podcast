"""Tests for the RL training pipeline."""

import os
import pytest
import tempfile
from src.rl.trainer import (
    DPOTrainer, GRPOTrainer, SFTTrainer,
    TrainingConfig, TrainingMetrics
)


@pytest.fixture
def config(tmp_dir):
    return TrainingConfig(
        model_name="Qwen/Qwen2.5-7B-Instruct",
        output_dir=os.path.join(tmp_dir, "test_model"),
        num_epochs=2,
        batch_size=2,
        logging_steps=1,
    )


@pytest.fixture
def dpo_data():
    """Sample DPO training data."""
    return [
        {"prompt": "Write a podcast intro about AI", "chosen": "Welcome to AI Insights...", "rejected": "Hi."},
        {"prompt": "Explain ML basics", "chosen": "ML is a fascinating field...", "rejected": "ML is stuff."},
        {"prompt": "Discuss neural networks", "chosen": "Neural networks are inspired by...", "rejected": "Neurons."},
        {"prompt": "Cover deep learning", "chosen": "Deep learning uses layers...", "rejected": "Deep."},
    ]


@pytest.fixture
def grpo_data():
    """Sample GRPO prompts."""
    return [
        {"prompt": "Write a podcast intro about AI Safety"},
        {"prompt": "Explain reinforcement learning"},
        {"prompt": "Discuss the future of language models"},
    ]


@pytest.fixture
def sft_data():
    """Sample SFT training data."""
    return [
        {"text": "Topic: AI Safety\nHost: Welcome! Today we discuss AI safety..."},
        {"text": "Topic: ML\nHost: Machine learning is transforming everything..."},
    ]


class TestTrainingConfig:
    def test_defaults(self):
        config = TrainingConfig()
        assert config.learning_rate == 1e-6
        assert config.batch_size == 4
        assert config.beta == 0.1

    def test_to_dict(self):
        config = TrainingConfig()
        d = config.to_dict()
        assert isinstance(d, dict)
        assert d["learning_rate"] == 1e-6

    def test_save_and_load(self, tmp_dir):
        config = TrainingConfig(learning_rate=5e-5)
        path = os.path.join(tmp_dir, "config.json")
        config.save(path)

        loaded = TrainingConfig.load(path)
        assert loaded.learning_rate == 5e-5


class TestTrainingMetrics:
    def test_to_dict(self):
        m = TrainingMetrics(loss=0.5, reward_accuracy=0.8, epoch=1)
        d = m.to_dict()
        assert d["loss"] == 0.5
        assert d["reward_accuracy"] == 0.8


class TestDPOTrainer:
    def test_simulated_training(self, config, dpo_data):
        """DPO trainer should work in simulated mode without torch."""
        trainer = DPOTrainer(config)
        metrics = trainer.train(dpo_data)

        assert isinstance(metrics, TrainingMetrics)
        assert metrics.loss >= 0
        assert len(trainer.metrics_history) > 0

    def test_checkpoint_saved(self, config, dpo_data):
        trainer = DPOTrainer(config)
        trainer.train(dpo_data)

        # Check checkpoint directory exists
        checkpoints = list((p for p in os.listdir(config.output_dir) if p.startswith("checkpoint")))
        assert len(checkpoints) > 0

    def test_generate_simulated(self, config):
        trainer = DPOTrainer(config)
        trainer._setup_model()
        results = trainer.generate(["Test prompt"], num_generations=2)

        assert len(results) == 1
        assert len(results[0]) == 2

    def test_evaluate_simulated(self, config, dpo_data):
        trainer = DPOTrainer(config)
        trainer._setup_model()
        metrics = trainer.evaluate(dpo_data)
        assert metrics.reward_accuracy > 0


class TestGRPOTrainer:
    def test_simulated_training(self, config, grpo_data):
        trainer = GRPOTrainer(config)
        metrics = trainer.train(grpo_data)

        assert isinstance(metrics, TrainingMetrics)

    def test_with_reward_model(self, config, grpo_data):
        """Should accept a reward model."""
        from unittest.mock import MagicMock
        reward_model = MagicMock()
        reward_model.compute_reward.return_value = 0.8

        trainer = GRPOTrainer(config, reward_model=reward_model)
        metrics = trainer.train(grpo_data)
        assert isinstance(metrics, TrainingMetrics)


class TestSFTTrainer:
    def test_simulated_training(self, config, sft_data):
        trainer = SFTTrainer(config)
        metrics = trainer.train(sft_data)

        assert isinstance(metrics, TrainingMetrics)
        assert metrics.loss >= 0

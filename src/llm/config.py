"""
LLM Configuration

Defines supported providers and models with their characteristics.
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    ANTHROPIC = "anthropic"     # Claude - highest quality
    TOGETHER = "together"       # Together.ai - Qwen, Llama, Mixtral
    FIREWORKS = "fireworks"     # Fireworks.ai - fast inference
    GROQ = "groq"               # Groq - ultra-fast (LPU)
    OLLAMA = "ollama"           # Local - free but slower
    OPENAI = "openai"           # OpenAI - GPT models


# Model recommendations per task type
RECOMMENDED_MODELS = {
    "dialogue_generation": {
        # Best quality for creative writing
        LLMProvider.ANTHROPIC: "claude-sonnet-4-20250514",
        # Best open-source for multilingual creative
        LLMProvider.TOGETHER: "Qwen/Qwen2.5-72B-Instruct",
        LLMProvider.FIREWORKS: "accounts/fireworks/models/qwen2p5-72b-instruct",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.OLLAMA: "qwen2.5:32b",
        LLMProvider.OPENAI: "gpt-4o",
    },
    "fact_extraction": {
        # Faster models for extraction tasks
        LLMProvider.ANTHROPIC: "claude-sonnet-4-20250514",
        LLMProvider.TOGETHER: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        LLMProvider.FIREWORKS: "accounts/fireworks/models/llama-v3p3-70b-instruct",
        LLMProvider.GROQ: "llama-3.3-70b-versatile",
        LLMProvider.OLLAMA: "llama3.2:latest",
        LLMProvider.OPENAI: "gpt-4o-mini",
    },
    "topic_expansion": {
        # Smaller models sufficient for topic expansion
        LLMProvider.ANTHROPIC: "claude-sonnet-4-20250514",
        LLMProvider.TOGETHER: "Qwen/Qwen2.5-32B-Instruct",
        LLMProvider.FIREWORKS: "accounts/fireworks/models/qwen2p5-32b-instruct",
        LLMProvider.GROQ: "llama-3.1-8b-instant",
        LLMProvider.OLLAMA: "qwen2.5:7b",
        LLMProvider.OPENAI: "gpt-4o-mini",
    }
}

# Cost per 1M tokens (input/output) - approximate as of Feb 2025
MODEL_COSTS = {
    # Anthropic
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku-20241022": {"input": 0.8, "output": 4.0},

    # Together.ai (much cheaper!)
    "Qwen/Qwen2.5-72B-Instruct": {"input": 0.9, "output": 0.9},
    "Qwen/Qwen2.5-32B-Instruct": {"input": 0.4, "output": 0.4},
    "meta-llama/Llama-3.3-70B-Instruct-Turbo": {"input": 0.88, "output": 0.88},

    # Groq (free tier available!)
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},

    # OpenAI
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


@dataclass
class LLMConfig:
    """
    Configuration for LLM client.

    Attributes:
        provider: Which provider to use
        model: Specific model name (None = use recommended)
        api_key: API key (None = from env)
        api_base: Custom API base URL (for Ollama, proxies)
        task_type: Type of task (affects model recommendation)
        temperature: Creativity (0.0 = deterministic, 1.0 = creative)
        max_tokens: Maximum output tokens
        timeout: Request timeout in seconds
        retry_count: Number of retries on failure
    """
    provider: LLMProvider = field(default_factory=lambda: LLMProvider(
        os.getenv("LLM_PROVIDER", "anthropic")
    ))
    model: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    task_type: str = "dialogue_generation"
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 120
    retry_count: int = 3

    def __post_init__(self):
        # Auto-select model if not specified
        if self.model is None:
            self.model = RECOMMENDED_MODELS.get(
                self.task_type,
                RECOMMENDED_MODELS["dialogue_generation"]
            ).get(self.provider)

        # Get API key from env if not provided
        if self.api_key is None:
            env_key_map = {
                LLMProvider.ANTHROPIC: "ANTHROPIC_API_KEY",
                LLMProvider.TOGETHER: "TOGETHER_API_KEY",
                LLMProvider.FIREWORKS: "FIREWORKS_API_KEY",
                LLMProvider.GROQ: "GROQ_API_KEY",
                LLMProvider.OPENAI: "OPENAI_API_KEY",
                LLMProvider.OLLAMA: None,  # No key needed
            }
            env_var = env_key_map.get(self.provider)
            if env_var:
                self.api_key = os.getenv(env_var)

        # Set default API base for Ollama
        if self.provider == LLMProvider.OLLAMA and self.api_base is None:
            self.api_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def get_cost_per_1m_tokens(self) -> Dict[str, float]:
        """Get cost per 1M tokens for this model"""
        return MODEL_COSTS.get(self.model, {"input": 0.0, "output": 0.0})

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request"""
        costs = self.get_cost_per_1m_tokens()
        return (
            (input_tokens / 1_000_000) * costs["input"] +
            (output_tokens / 1_000_000) * costs["output"]
        )

    @classmethod
    def cheap(cls, task_type: str = "dialogue_generation") -> "LLMConfig":
        """
        Get a cheap configuration for experiments.
        Uses Together.ai with Qwen by default.
        """
        return cls(
            provider=LLMProvider.TOGETHER,
            task_type=task_type,
            temperature=0.7
        )

    @classmethod
    def fast(cls, task_type: str = "dialogue_generation") -> "LLMConfig":
        """
        Get a fast configuration (Groq).
        Good for iteration and testing.
        """
        return cls(
            provider=LLMProvider.GROQ,
            task_type=task_type,
            temperature=0.7
        )

    @classmethod
    def quality(cls, task_type: str = "dialogue_generation") -> "LLMConfig":
        """
        Get a high-quality configuration (Claude).
        Best for final outputs.
        """
        return cls(
            provider=LLMProvider.ANTHROPIC,
            task_type=task_type,
            temperature=0.7
        )

    @classmethod
    def local(cls, task_type: str = "dialogue_generation") -> "LLMConfig":
        """
        Get a local configuration (Ollama).
        Free but requires local setup.
        """
        return cls(
            provider=LLMProvider.OLLAMA,
            task_type=task_type,
            temperature=0.7
        )

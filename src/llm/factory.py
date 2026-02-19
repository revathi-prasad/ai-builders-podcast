"""
LLM Client Factory

Creates the appropriate client based on configuration.
"""

from typing import Optional

from .base import BaseLLMClient
from .config import LLMConfig, LLMProvider


def get_llm_client(config: Optional[LLMConfig] = None) -> BaseLLMClient:
    """
    Get an LLM client based on configuration.

    Args:
        config: LLM configuration. If None, uses defaults from environment.

    Returns:
        Configured LLM client ready to use

    Usage:
        # Default (from env)
        client = get_llm_client()

        # Cheap config (Together.ai)
        client = get_llm_client(LLMConfig.cheap())

        # Fast config (Groq)
        client = get_llm_client(LLMConfig.fast())

        # Quality config (Claude)
        client = get_llm_client(LLMConfig.quality())

        # Local (Ollama)
        client = get_llm_client(LLMConfig.local())

        # Custom
        client = get_llm_client(LLMConfig(
            provider=LLMProvider.TOGETHER,
            model="Qwen/Qwen2.5-72B-Instruct",
            temperature=0.8
        ))
    """
    if config is None:
        config = LLMConfig()

    # Import providers lazily to avoid circular imports
    from .providers.anthropic_client import AnthropicClient
    from .providers.openai_compatible import OpenAICompatibleClient

    if config.provider == LLMProvider.ANTHROPIC:
        return AnthropicClient(config)
    else:
        # Together, Fireworks, Groq, OpenAI, Ollama all use OpenAI-compatible API
        return OpenAICompatibleClient(config)


def get_cheap_client(task_type: str = "dialogue_generation") -> BaseLLMClient:
    """Shortcut for cheap experiments (Together.ai with Qwen)"""
    return get_llm_client(LLMConfig.cheap(task_type))


def get_fast_client(task_type: str = "dialogue_generation") -> BaseLLMClient:
    """Shortcut for fast iteration (Groq)"""
    return get_llm_client(LLMConfig.fast(task_type))


def get_quality_client(task_type: str = "dialogue_generation") -> BaseLLMClient:
    """Shortcut for high-quality output (Claude)"""
    return get_llm_client(LLMConfig.quality(task_type))


def get_local_client(task_type: str = "dialogue_generation") -> BaseLLMClient:
    """Shortcut for local inference (Ollama)"""
    return get_llm_client(LLMConfig.local(task_type))

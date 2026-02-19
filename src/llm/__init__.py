"""
Model-Agnostic LLM Interface

Supports multiple providers:
- Claude (Anthropic) - High quality, expensive
- Together.ai - Qwen, Llama, Mixtral
- Fireworks - Fast inference
- Groq - Ultra-fast inference
- Ollama - Local models (free but slower)

Usage:
    from src.llm import get_llm_client, LLMConfig

    # Use default (from env)
    client = get_llm_client()
    response = await client.generate("Write a podcast script...")

    # Override for specific task
    cheap_client = get_llm_client(LLMConfig(provider="together", model="Qwen/Qwen2.5-72B-Instruct"))
"""

from .config import LLMConfig, LLMProvider
from .base import BaseLLMClient, LLMResponse
from .factory import get_llm_client

__all__ = [
    "LLMConfig",
    "LLMProvider",
    "BaseLLMClient",
    "LLMResponse",
    "get_llm_client"
]

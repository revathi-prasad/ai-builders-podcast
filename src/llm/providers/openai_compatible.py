"""
OpenAI-Compatible Client Implementation

Works with:
- Together.ai
- Fireworks.ai
- Groq
- OpenAI
- vLLM
- Any OpenAI-compatible API
"""

import time
from typing import Optional, List, AsyncGenerator

from ..base import BaseLLMClient, LLMResponse, LLMMessage
from ..config import LLMConfig, LLMProvider, MODEL_COSTS


# API base URLs for different providers
PROVIDER_URLS = {
    LLMProvider.TOGETHER: "https://api.together.xyz/v1",
    LLMProvider.FIREWORKS: "https://api.fireworks.ai/inference/v1",
    LLMProvider.GROQ: "https://api.groq.com/openai/v1",
    LLMProvider.OPENAI: "https://api.openai.com/v1",
}


class OpenAICompatibleClient(BaseLLMClient):
    """
    Client for OpenAI-compatible APIs.

    Supports Together.ai, Fireworks, Groq, OpenAI, and any OpenAI-compatible API.
    """

    def __init__(self, config: LLMConfig):
        super().__init__()
        self.config = config

        # Lazy import
        try:
            import openai
            self._openai = openai
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        # Determine API base URL
        api_base = config.api_base or PROVIDER_URLS.get(config.provider)
        if not api_base:
            raise ValueError(f"Unknown provider: {config.provider}")

        # API key not needed for Ollama
        api_key = config.api_key
        if config.provider == LLMProvider.OLLAMA:
            api_key = "ollama"  # Ollama doesn't need a real key

        if not api_key and config.provider != LLMProvider.OLLAMA:
            raise ValueError(f"API key not set for {config.provider}")

        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=config.timeout
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate a response"""
        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
        }

        if stop_sequences:
            kwargs["stop"] = stop_sequences

        response = await self.client.chat.completions.create(**kwargs)

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract content
        content = response.choices[0].message.content if response.choices else ""

        # Calculate cost
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        costs = MODEL_COSTS.get(self.config.model, {"input": 0.5, "output": 0.5})
        estimated_cost = (
            (input_tokens / 1_000_000) * costs["input"] +
            (output_tokens / 1_000_000) * costs["output"]
        )

        llm_response = LLMResponse(
            content=content,
            model=self.config.model,
            provider=self.config.provider.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            raw_response={
                "id": response.id,
                "finish_reason": response.choices[0].finish_reason if response.choices else None
            }
        )

        self.usage_stats.add(llm_response)
        return llm_response

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a response"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "stream": True,
        }

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Multi-turn chat"""
        start_time = time.time()

        formatted_messages = [msg.to_dict() for msg in messages]

        kwargs = {
            "model": self.config.model,
            "messages": formatted_messages,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
        }

        response = await self.client.chat.completions.create(**kwargs)

        latency_ms = int((time.time() - start_time) * 1000)
        content = response.choices[0].message.content if response.choices else ""

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        costs = MODEL_COSTS.get(self.config.model, {"input": 0.5, "output": 0.5})
        estimated_cost = (
            (input_tokens / 1_000_000) * costs["input"] +
            (output_tokens / 1_000_000) * costs["output"]
        )

        llm_response = LLMResponse(
            content=content,
            model=self.config.model,
            provider=self.config.provider.value,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            raw_response={
                "id": response.id,
                "finish_reason": response.choices[0].finish_reason if response.choices else None
            }
        )

        self.usage_stats.add(llm_response)
        return llm_response

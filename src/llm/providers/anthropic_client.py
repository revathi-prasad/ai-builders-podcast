"""
Anthropic (Claude) Client Implementation
"""

import time
from typing import Optional, List, AsyncGenerator

from ..base import BaseLLMClient, LLMResponse, LLMMessage
from ..config import LLMConfig, MODEL_COSTS


class AnthropicClient(BaseLLMClient):
    """
    Client for Anthropic's Claude models.

    Best for: High-quality creative writing, complex reasoning
    Cost: ~$3/1M input, $15/1M output for Sonnet
    """

    def __init__(self, config: LLMConfig):
        super().__init__()
        self.config = config

        # Lazy import
        try:
            import anthropic
            self._anthropic = anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        if not config.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = anthropic.AsyncAnthropic(api_key=config.api_key)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate a response using Claude"""
        start_time = time.time()

        kwargs = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences

        response = await self.client.messages.create(**kwargs)

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract content
        content = response.content[0].text if response.content else ""

        # Calculate cost
        costs = MODEL_COSTS.get(self.config.model, {"input": 3.0, "output": 15.0})
        estimated_cost = (
            (response.usage.input_tokens / 1_000_000) * costs["input"] +
            (response.usage.output_tokens / 1_000_000) * costs["output"]
        )

        llm_response = LLMResponse(
            content=content,
            model=self.config.model,
            provider="anthropic",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            raw_response={"id": response.id, "stop_reason": response.stop_reason}
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
        """Stream a response using Claude"""
        kwargs = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Multi-turn chat with Claude"""
        start_time = time.time()

        # Separate system message if present
        system_prompt = None
        chat_messages = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                chat_messages.append(msg.to_dict())

        kwargs = {
            "model": self.config.model,
            "max_tokens": max_tokens or self.config.max_tokens,
            "temperature": temperature if temperature is not None else self.config.temperature,
            "messages": chat_messages,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self.client.messages.create(**kwargs)

        latency_ms = int((time.time() - start_time) * 1000)
        content = response.content[0].text if response.content else ""

        costs = MODEL_COSTS.get(self.config.model, {"input": 3.0, "output": 15.0})
        estimated_cost = (
            (response.usage.input_tokens / 1_000_000) * costs["input"] +
            (response.usage.output_tokens / 1_000_000) * costs["output"]
        )

        llm_response = LLMResponse(
            content=content,
            model=self.config.model,
            provider="anthropic",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
            raw_response={"id": response.id, "stop_reason": response.stop_reason}
        )

        self.usage_stats.add(llm_response)
        return llm_response

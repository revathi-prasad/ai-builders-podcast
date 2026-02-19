"""
Base LLM Client Interface

Defines the abstract interface all LLM clients must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncGenerator
from datetime import datetime


@dataclass
class LLMMessage:
    """A message in a conversation"""
    role: str  # "system", "user", "assistant"
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """
    Response from an LLM.

    Includes metadata for cost tracking and RL experiments.
    """
    content: str
    model: str
    provider: str

    # Token counts
    input_tokens: int = 0
    output_tokens: int = 0

    # Timing
    latency_ms: int = 0

    # Cost tracking
    estimated_cost: float = 0.0

    # For RL: raw response data
    raw_response: Dict[str, Any] = field(default_factory=dict)

    # Timestamp
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMUsageStats:
    """Track usage across requests for cost monitoring"""
    total_requests: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    total_latency_ms: int = 0

    def add(self, response: LLMResponse) -> None:
        self.total_requests += 1
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        self.total_cost += response.estimated_cost
        self.total_latency_ms += response.latency_ms

    @property
    def avg_latency_ms(self) -> float:
        if self.total_requests == 0:
            return 0
        return self.total_latency_ms / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost": round(self.total_cost, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }


class BaseLLMClient(ABC):
    """
    Abstract base class for LLM clients.

    All providers must implement these methods to be interchangeable.
    """

    def __init__(self):
        self.usage_stats = LLMUsageStats()

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            temperature: Override default temperature
            max_tokens: Override default max tokens
            stop_sequences: Optional stop sequences

        Returns:
            LLMResponse with content and metadata
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from the LLM.

        Yields:
            Text chunks as they're generated
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Multi-turn chat with the LLM.

        Args:
            messages: List of messages in the conversation
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            LLMResponse with assistant's reply
        """
        pass

    def get_usage_stats(self) -> LLMUsageStats:
        """Get current usage statistics"""
        return self.usage_stats

    def reset_usage_stats(self) -> None:
        """Reset usage statistics"""
        self.usage_stats = LLMUsageStats()

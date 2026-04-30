"""Injectable dependencies for graph nodes (LLM, Tavily, cache)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from langchain_core.messages import BaseMessage

from advisor.llm_usage import TokenUsageAccumulator

if TYPE_CHECKING:
    from tavily import TavilyClient


@dataclass
class AdvisorDeps:
    """Replace callables in tests; produksi pakai ChatOpenAI atau ChatGoogleGenerativeAI."""

    invoke_llm_a: Callable[[list[BaseMessage]], str]
    invoke_llm_c: Callable[[list[BaseMessage]], str]
    tavily_client: TavilyClient | None = None
    cache: Any | None = None  # MemoryTTLCache
    model_name_a: str = "gpt-4o-mini"
    model_name_c: str = "gpt-4o"
    token_usage: TokenUsageAccumulator | None = None

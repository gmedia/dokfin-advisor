"""Accumulate LLM token usage from LangChain AIMessage (usage_metadata / legacy metadata)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from advisor.schemas.output import TokenUsage


def _extract_turn_tokens(msg: Any) -> tuple[int, int] | None:
    um = getattr(msg, "usage_metadata", None)
    if isinstance(um, dict):
        inp = int(um.get("input_tokens") or 0)
        out = int(um.get("output_tokens") or 0)
        if inp or out:
            return inp, out
    rmeta = getattr(msg, "response_metadata", None) or {}
    if not isinstance(rmeta, dict):
        return None
    tu = rmeta.get("token_usage")
    if isinstance(tu, dict):
        inp = int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0)
        out = int(tu.get("completion_tokens") or tu.get("output_tokens") or 0)
        if inp or out:
            return inp, out
    return None


@dataclass
class TokenUsageAccumulator:
    """Mutable per-job counters; reset at start of each `run_advisor` call."""

    node_a_input: int = 0
    node_a_output: int = 0
    node_c_input: int = 0
    node_c_output: int = 0

    def reset(self) -> None:
        self.node_a_input = 0
        self.node_a_output = 0
        self.node_c_input = 0
        self.node_c_output = 0

    def add_node_a(self, response: Any) -> None:
        t = _extract_turn_tokens(response)
        if t:
            self.node_a_input += t[0]
            self.node_a_output += t[1]

    def add_node_c(self, response: Any) -> None:
        t = _extract_turn_tokens(response)
        if t:
            self.node_c_input += t[0]
            self.node_c_output += t[1]

    def is_empty(self) -> bool:
        return not (
            self.node_a_input or self.node_a_output or self.node_c_input or self.node_c_output
        )

    def to_token_usage(self) -> TokenUsage | None:
        if self.is_empty():
            return None
        total = self.node_a_input + self.node_a_output + self.node_c_input + self.node_c_output
        return TokenUsage(
            node_a_input=self.node_a_input or None,
            node_a_output=self.node_a_output or None,
            node_c_input=self.node_c_input or None,
            node_c_output=self.node_c_output or None,
            total=total or None,
        )

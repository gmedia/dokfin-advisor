"""Rough IDR cost from token counts (env-driven; not billing truth)."""

from __future__ import annotations

import os

from advisor.llm_usage import TokenUsageAccumulator


def _fenv(name: str) -> float | None:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _sanitized_model_key(model: str) -> str:
    return model.replace("-", "_").replace(".", "_")


def _openai_rates(model: str) -> tuple[float | None, float | None]:
    key = _sanitized_model_key(model)
    inp = _fenv(f"OPENAI_PRICE_{key}_INPUT_PER_M_IDR")
    out = _fenv(f"OPENAI_PRICE_{key}_OUTPUT_PER_M_IDR")
    if inp is not None and out is not None:
        return inp, out
    return _fenv("OPENAI_PRICE_INPUT_PER_M_IDR"), _fenv("OPENAI_PRICE_OUTPUT_PER_M_IDR")


def _google_rates(model: str) -> tuple[float | None, float | None]:
    key = _sanitized_model_key(model)
    inp = _fenv(f"GOOGLE_PRICE_{key}_INPUT_PER_M_IDR")
    out = _fenv(f"GOOGLE_PRICE_{key}_OUTPUT_PER_M_IDR")
    if inp is not None and out is not None:
        return inp, out
    return _fenv("GOOGLE_PRICE_INPUT_PER_M_IDR"), _fenv("GOOGLE_PRICE_OUTPUT_PER_M_IDR")


def estimate_cost_idr(
    acc: TokenUsageAccumulator,
    *,
    model_a: str,
    model_c: str,
    llm_provider: str | None = None,
) -> float | None:
    """IDR per 1M tokens. Model-specific keys optional; fallback to generic env."""

    prov = (llm_provider or os.environ.get("LLM_PROVIDER", "openai")).strip().lower()
    use_google = prov in ("google", "gemini", "genai")
    rates_for = _google_rates if use_google else _openai_rates

    ain, aout = rates_for(model_a)
    cin, cout = rates_for(model_c)
    if ain is None or aout is None or cin is None or cout is None:
        return None

    cost_a = (acc.node_a_input * ain + acc.node_a_output * aout) / 1_000_000
    cost_c = (acc.node_c_input * cin + acc.node_c_output * cout) / 1_000_000
    return round(cost_a + cost_c, 2)

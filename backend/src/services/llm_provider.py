"""Backward-compatibility shim — import from src.services.llm instead."""

from src.services.llm import (  # noqa: F401
    LLMProvider,
    DeepSeekProvider,
    GeminiProvider,
    FallbackProvider,
    get_llm_provider,
    get_reasoning_provider,
    reset_llm_provider,
)

"""Factory for the active LLM provider.

Architecture: Gemini 2.5 Flash (primary) + DeepSeek NIM (emergency fallback)
- Gemini 2.5 Flash: ALL workloads (packages, roadmaps, coaching, governance, reasoning)
- DeepSeek NIM: emergency fallback only when Gemini fails
"""

from __future__ import annotations

import logging
from typing import Optional

from src.core.config import settings

from .deepseek_provider import DeepSeekProvider
from .fallback_provider import FallbackProvider
from .gemini_provider import GeminiProvider
from .provider import LLMProvider

logger = logging.getLogger(__name__)

_provider: Optional[LLMProvider] = None
_reasoning_provider: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """Return the primary LLM provider (Gemini Flash with DeepSeek fallback)."""
    global _provider
    if _provider is None:
        _provider = _create_primary_provider()
    return _provider


def get_reasoning_provider() -> LLMProvider:
    """Return the reasoning provider (Gemini 2.5 Flash with DeepSeek fallback).

    NOTE: Unified to Gemini Flash for single-model architecture.
    Previously used Gemini Pro; now consolidated to Gemini Flash for all workloads.
    """
    global _reasoning_provider
    if _reasoning_provider is None:
        _reasoning_provider = _create_primary_provider()
    return _reasoning_provider


def _create_gemini(model: str) -> Optional[GeminiProvider]:
    """Create a Gemini provider if API key is available."""
    if not settings.GEMINI_API_KEY:
        return None
    return GeminiProvider(
        api_key=settings.GEMINI_API_KEY,
        model=model,
        timeout_s=settings.GEMINI_TIMEOUT,
        max_retries=settings.GEMINI_MAX_RETRIES,
    )


def _create_deepseek() -> DeepSeekProvider:
    """Create the DeepSeek NIM fallback provider."""
    if not settings.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY is required for DeepSeek fallback.")
    return DeepSeekProvider(
        api_key=settings.NVIDIA_API_KEY,
        base_url=settings.NVIDIA_NIM_BASE_URL,
        model=settings.DEEPSEEK_MODEL,
        timeout_s=settings.CLAUDE_TIMEOUT,
        max_retries=settings.CLAUDE_MAX_RETRIES,
    )


def _create_primary_provider() -> LLMProvider:
    """Create primary provider: Gemini 2.5 Flash + DeepSeek fallback."""
    gemini = _create_gemini(settings.GEMINI_PRIMARY_MODEL)
    deepseek = _create_deepseek()

    if gemini:
        logger.info(
            "Creating LLM provider: Gemini %s (primary) + DeepSeek (fallback)",
            settings.GEMINI_PRIMARY_MODEL,
        )
        return FallbackProvider(primary=gemini, fallback=deepseek)
    else:
        logger.warning("GEMINI_API_KEY not set — using DeepSeek NIM as primary")
        return deepseek


def _create_reasoning_provider() -> LLMProvider:
    """Create reasoning provider: Gemini 2.5 Flash + DeepSeek fallback.

    NOTE: Consolidated to Gemini Flash for single-model architecture.
    """
    gemini = _create_gemini(settings.GEMINI_PRIMARY_MODEL)
    deepseek = _create_deepseek()

    if gemini:
        logger.info(
            "Creating reasoning LLM provider: Gemini %s (primary) + DeepSeek (fallback)",
            settings.GEMINI_PRIMARY_MODEL,
        )
        return FallbackProvider(primary=gemini, fallback=deepseek)
    else:
        logger.warning("GEMINI_API_KEY not set — using DeepSeek NIM for reasoning")
        return deepseek


def reset_llm_provider() -> None:
    global _provider, _reasoning_provider
    _provider = None
    _reasoning_provider = None

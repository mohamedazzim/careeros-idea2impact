"""
Domain types for Claude resource governance — typed constants replacing
stringly-typed domain scattering across the codebase.

Phase 4D: Domain-aware orchestration enums.
"""
from enum import Enum


class ClaudeDomain(str, Enum):
    """Resource-governance domains for Claude orchestration.

    Each domain has its own concurrency semaphore, token budget, retry
    strategy, and observability namespace.
    """

    EVALUATION = "evaluation"
    """ATS scoring, recruiter review, skill gaps, semantic fit, resume analysis."""

    STRATEGY = "strategy"
    """Career strategy, roadmaps, recommendations, opportunity prioritization."""

    INTERVIEW = "interview"
    """Interview simulation, adaptive questioning, critique, behavioral analysis."""

    GENERAL = "general"
    """Fallback for generic utilities and unclassified workloads."""


# ── Category → Domain Mapping ────────────────────────────────────────
# Every reasoning_pipeline category maps to exactly one ClaudeDomain.

CATEGORY_TO_DOMAIN: dict[str, ClaudeDomain] = {
    # ── Evaluation domain ──
    "ats": ClaudeDomain.EVALUATION,
    "scoring": ClaudeDomain.EVALUATION,
    "evaluation": ClaudeDomain.EVALUATION,
    "recruiter": ClaudeDomain.EVALUATION,
    "semantic_fit": ClaudeDomain.EVALUATION,
    "resume": ClaudeDomain.EVALUATION,
    "achievement": ClaudeDomain.EVALUATION,

    # ── Strategy domain ──
    "strategy": ClaudeDomain.STRATEGY,
    "recommendation": ClaudeDomain.STRATEGY,
    "roadmap": ClaudeDomain.STRATEGY,
    "prioritization": ClaudeDomain.STRATEGY,
    "career": ClaudeDomain.STRATEGY,

    # ── Interview domain ──
    "interview": ClaudeDomain.INTERVIEW,
    "behavioral": ClaudeDomain.INTERVIEW,
    "technical_interview": ClaudeDomain.INTERVIEW,
    "mock_interview": ClaudeDomain.INTERVIEW,

    # ── General domain ──
    "general": ClaudeDomain.GENERAL,
    "chat": ClaudeDomain.GENERAL,
    "qa": ClaudeDomain.GENERAL,
}


# ── Domain Concurrency Defaults ──────────────────────────────────────

DOMAIN_SEMAPHORE_DEFAULTS: dict[ClaudeDomain, int] = {
    ClaudeDomain.EVALUATION: 2,
    ClaudeDomain.STRATEGY: 3,
    ClaudeDomain.INTERVIEW: 2,
    ClaudeDomain.GENERAL: 4,
}

# ── Domain Token Budgets (per session, approximate) ─────────────────

DOMAIN_TOKEN_BUDGETS: dict[ClaudeDomain, int] = {
    ClaudeDomain.EVALUATION: 200_000,
    ClaudeDomain.STRATEGY: 150_000,
    ClaudeDomain.INTERVIEW: 250_000,
    ClaudeDomain.GENERAL: 100_000,
}

# ── Domain Retry Config ─────────────────────────────────────────────

DOMAIN_RETRY_DEFAULTS: dict[ClaudeDomain, int] = {
    ClaudeDomain.EVALUATION: 2,
    ClaudeDomain.STRATEGY: 2,
    ClaudeDomain.INTERVIEW: 3,
    ClaudeDomain.GENERAL: 1,
}


def resolve_domain(category: str) -> ClaudeDomain:
    """Resolve a reasoning pipeline category to its governed ClaudeDomain."""
    if not category:
        return ClaudeDomain.GENERAL
    domain = CATEGORY_TO_DOMAIN.get(category.lower())
    if domain is not None:
        return domain
    return ClaudeDomain.GENERAL


def is_valid_domain(value: str) -> bool:
    """Validate that a string is a known ClaudeDomain value."""
    return value in set(d.value for d in ClaudeDomain)


__all__ = [
    "ClaudeDomain",
    "CATEGORY_TO_DOMAIN",
    "DOMAIN_SEMAPHORE_DEFAULTS",
    "DOMAIN_TOKEN_BUDGETS",
    "DOMAIN_RETRY_DEFAULTS",
    "resolve_domain",
    "is_valid_domain",
]

"""Phase 5 — Opportunity Services Package.

Lazy exports for match engine, urgency, prioritization, and market signals.
"""


def __getattr__(name: str):
    if name == "opportunity_match_engine":
        from src.services.opportunity.opportunity_match_engine import get_opportunity_match_engine
        return get_opportunity_match_engine()
    if name == "urgency_engine":
        from src.services.opportunity.urgency_engine import get_urgency_engine
        return get_urgency_engine()
    if name == "prioritization_engine":
        from src.services.opportunity.prioritization_engine import get_prioritization_engine
        return get_prioritization_engine()
    if name == "market_signal_engine":
        from src.services.opportunity.market_signal_engine import get_market_signal_engine
        return get_market_signal_engine()
    if name == "opportunity_memory":
        from src.services.opportunity.opportunity_memory import get_opportunity_memory
        return get_opportunity_memory()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

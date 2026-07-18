"""Phase 5 — Explainability Package."""

def __getattr__(name: str):
    if name == "explainability_service":
        from src.explainability.explainability_service import get_explainability_service
        return get_explainability_service()
    if name == "ExplainabilityService":
        from src.explainability.explainability_service import ExplainabilityService
        return ExplainabilityService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

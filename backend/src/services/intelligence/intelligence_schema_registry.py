"""
Intelligence schema registry — maps schema names to pydantic models.

Used by with_structured_output() for deterministic Claude output parsing.
"""
from typing import Dict, Type, Optional
from src.schemas.evaluation import ResumeEvaluation

_registry: Dict[str, Type] = {
    "ResumeEvaluation": ResumeEvaluation,
}

def register(name: str, schema: Type) -> None:
    _registry[name] = schema

def get(name: str) -> Optional[Type]:
    return _registry.get(name)

def list_all() -> Dict[str, Type]:
    return dict(_registry)

"""
Schema registry for Claude structured output schemas.

Maps schema names to pydantic models for with_structured_output().
Ensures consistent schema usage across all intelligence pipelines.
"""
from typing import Dict, Type, Optional
from src.schemas.evaluation import ResumeEvaluation


_registry: Dict[str, Type] = {
    "ResumeEvaluation": ResumeEvaluation,
}


def register_schema(name: str, schema: Type) -> None:
    _registry[name] = schema


def get_schema(name: str) -> Optional[Type]:
    return _registry.get(name)


def list_schemas() -> Dict[str, Type]:
    return dict(_registry)

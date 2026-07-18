"""
Streaming readiness boundaries — preparation for future streaming interview features.

Defines interfaces and data contracts for:
- Token-level streaming of Claude responses
- Partial critique streaming during answer evaluation
- Live interviewer reaction events
- Incremental evaluation updates
- Interruption-safe orchestration hooks

Phase 4D Hardening: Streaming preparation boundaries.
DO NOT implement websocket or SSE transport yet.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class StreamEventType(str, Enum):
    TOKEN = "token"
    PARTIAL_CRITIQUE = "partial_critique"
    EVALUATION_PROGRESS = "evaluation_progress"
    DIFFICULTY_UPDATE = "difficulty_update"
    INTERRUPTION = "interruption"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class StreamEvent:
    event_type: StreamEventType
    session_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    sequence: int = 0


@dataclass
class StreamToken:
    text: str
    finish_reason: Optional[str] = None
    index: int = 0


@dataclass
class PartialCritique:
    dimension: str
    score_so_far: float = 0.0
    observations: List[str] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class EvaluationProgress:
    dimensions_evaluated: int = 0
    total_dimensions: int = 0
    current_dimension: str = ""
    estimated_remaining_seconds: float = 0.0


class StreamingOrchestrator:
    """Streaming orchestration interface. Implementation reserved for Phase 5+."""

    def __init__(self):
        self._token_buffer: List[StreamToken] = []
        self._critique_buffer: List[PartialCritique] = []
        self._listeners: Dict[str, List[Callable]] = {}

    def register_listener(self, event_type: StreamEventType, callback: Callable) -> None:
        if event_type.value not in self._listeners:
            self._listeners[event_type.value] = []
        self._listeners[event_type.value].append(callback)

    def buffer_token(self, token: StreamToken) -> None:
        self._token_buffer.append(token)

    def buffer_critique(self, critique: PartialCritique) -> None:
        self._critique_buffer.append(critique)

    def flush_buffer(self) -> List[StreamToken]:
        tokens = list(self._token_buffer)
        self._token_buffer.clear()
        return tokens

    @property
    def streaming_capable(self) -> bool:
        return False  # Not yet implemented

    async def emit(self, event: StreamEvent) -> None:
        pass  # Reserved for transport layer


_svc: StreamingOrchestrator | None = None


def get_streaming_orchestrator() -> StreamingOrchestrator:
    global _svc
    if _svc is None: _svc = StreamingOrchestrator()
    return _svc


def __getattr__(name: str):
    if name == "streaming_orchestrator": return get_streaming_orchestrator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Phase 5 — Agent Observability.

Observability wrapper for all agents. Records execution counts,
autonomous actions, suppressions, confidence scores, and retries.
"""

from typing import Optional

from src.observability.metrics import (
    AGENT_EXECUTION_COUNT,
    AGENT_EXECUTION_LATENCY,
    AGENT_CONFIDENCE_GAUGE,
    AUTONOMOUS_ACTION_COUNT,
    NOTIFICATION_SUPPRESSION_COUNT,
    RECURSION_PREVENTION_COUNT,
    ORCHESTRATION_FAILURES,
    GRAPH_RESUME_COUNT,
    VOICE_CALL_LATENCY,
    OPPORTUNITY_PROCESSING_LATENCY,
    GOVERNANCE_DECISION_COUNT,
)


class AgentObservability:

    def record_agent_execution(self, agent_name: str, status: str = "completed") -> None:
        AGENT_EXECUTION_COUNT.labels(agent_name=agent_name, status=status).inc()

    def record_agent_latency(self, agent_name: str, duration_seconds: float) -> None:
        AGENT_EXECUTION_LATENCY.labels(agent_name=agent_name).observe(duration_seconds)

    def record_confidence(self, agent_name: str, confidence: float) -> None:
        AGENT_CONFIDENCE_GAUGE.labels(agent_name=agent_name).set(confidence)

    def record_autonomous_action(self, action_type: str, status: str) -> None:
        AUTONOMOUS_ACTION_COUNT.labels(action_type=action_type, status=status).inc()

    def record_suppression(self, reason: str) -> None:
        NOTIFICATION_SUPPRESSION_COUNT.labels(reason=reason).inc()

    def record_recursion_prevention(self) -> None:
        RECURSION_PREVENTION_COUNT.inc()

    def record_orchestration_failure(self, node_name: str, reason: str) -> None:
        ORCHESTRATION_FAILURES.labels(node_name=node_name, reason=reason).inc()

    def record_graph_resume(self, graph_name: str) -> None:
        GRAPH_RESUME_COUNT.labels(graph_name=graph_name).inc()

    def record_voice_call_latency(self, stage: str, duration_seconds: float) -> None:
        VOICE_CALL_LATENCY.labels(stage=stage).observe(duration_seconds)

    def record_opportunity_processing(self, stage: str, duration_seconds: float) -> None:
        OPPORTUNITY_PROCESSING_LATENCY.labels(stage=stage).observe(duration_seconds)

    def record_governance_decision(self, decision_type: str, verdict: str) -> None:
        GOVERNANCE_DECISION_COUNT.labels(decision_type=decision_type, verdict=verdict).inc()


# ── Singleton ────────────────────────────────────────────────────────

_obs: Optional[AgentObservability] = None


def get_agent_observability() -> AgentObservability:
    global _obs
    if _obs is None:
        _obs = AgentObservability()
    return _obs


def reset_agent_observability() -> None:
    global _obs
    _obs = None

"""Phase 5 — Multi-Agent Orchestration.

Lazy-loading agent registry. Each agent is a singleton with
state contracts, observable outputs, and governance integration.

Access via: from src.agents import opportunity_discovery_agent
"""


def __getattr__(name: str):
    if name == "opportunity_discovery_agent":
        from src.agents.opportunity_discovery_agent import get_opportunity_discovery_agent
        return get_opportunity_discovery_agent()
    if name == "opportunity_scoring_agent":
        from src.agents.opportunity_scoring_agent import get_opportunity_scoring_agent
        return get_opportunity_scoring_agent()
    if name == "opportunity_prioritization_agent":
        from src.agents.opportunity_prioritization_agent import get_opportunity_prioritization_agent
        return get_opportunity_prioritization_agent()
    if name == "deadline_urgency_agent":
        from src.agents.deadline_urgency_agent import get_deadline_urgency_agent
        return get_deadline_urgency_agent()
    if name == "notification_decision_agent":
        from src.agents.notification_decision_agent import get_notification_decision_agent
        return get_notification_decision_agent()
    if name == "elevenlabs_voice_synthesis_agent":
        from src.agents.elevenlabs_voice_synthesis_agent import get_elevenlabs_voice_synthesis_agent
        return get_elevenlabs_voice_synthesis_agent()
    if name == "twilio_voice_agent":
        from src.agents.twilio_voice_agent import get_twilio_voice_agent
        return get_twilio_voice_agent()
    if name == "orchestration_governance_agent":
        from src.agents.orchestration_governance_agent import get_orchestration_governance_agent
        return get_orchestration_governance_agent()
    if name == "explainability_agent":
        from src.agents.explainability_agent import get_explainability_agent
        return get_explainability_agent()
    if name == "agent_observability":
        from src.agents.agent_observability import get_agent_observability
        return get_agent_observability()
    if name == "opportunity_alert_agent":
        from src.agents.opportunity_alert_agent import get_opportunity_alert_agent
        return get_opportunity_alert_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

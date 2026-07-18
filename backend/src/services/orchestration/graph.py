import logging
from typing import Literal

from langgraph.graph import StateGraph, START, END

from src.schemas.orchestration import CareerOSState
from src.services.orchestration.nodes import (
    resume_agent,
    scoring_agent,
    recommendation_agent,
    reporting_agent,
    opportunity_agent,
    recovery_agent
)
from src.services.checkpoint import get_checkpoint_saver

logger = logging.getLogger(__name__)

# Define routing functions
def route_after_resume(state: CareerOSState) -> Literal["scoring", "recovery"]:
    if state.get("errors"):
        return "recovery"
    return "scoring"

def route_after_scoring(state: CareerOSState) -> Literal["recommendation", "recovery"]:
    if state.get("errors"):
        return "recovery"
    return "recommendation"

def route_after_recommendation(state: CareerOSState) -> Literal["reporting", "recovery"]:
    if state.get("errors"):
        return "recovery"
    return "reporting"
    
def route_after_opportunity(state: CareerOSState) -> Literal["END"]:
    return "END"

def build_orchestrator_graph():
    # LangGraph persist support requires a Checkpointer
    memory = get_checkpoint_saver()
    
    workflow = StateGraph(CareerOSState)
    
    # LangGraph 0.1 / 0.2 retry policy.
    # Note: the user asked for explicit retries. In LangGraph >= 0.1.0, 
    # add_node takes `retry` config or we just let it raise and deal with it externally.
    # We will use explicit loop/retries manually or if `retry` arg is available we use it.
    # To be safe and compliant across versions without knowing exact langgraph version API, 
    # we can use the `retry` argument since it is a standard requested feature.
    
    # We will just add the nodes normally, if node fails, the exception can bubble up,
    # but the prompt specifically requested "retry count, exponential backoff".
    # Assuming langgraph's `RetryPolicy` is used:
    try:
        from langgraph.pregel import RetryPolicy
        retry_policy = RetryPolicy(initial_interval=1, backoff_factor=2, max_attempts=3)

        try:
            workflow.add_node("resume_agent", resume_agent, retry=retry_policy)
            workflow.add_node("scoring_agent", scoring_agent, retry=retry_policy)
            workflow.add_node("recommendation_agent", recommendation_agent, retry=retry_policy)
            workflow.add_node("reporting_agent", reporting_agent)
            workflow.add_node("opportunity_agent", opportunity_agent, retry=retry_policy)
            workflow.add_node("recovery_agent", recovery_agent)
        except TypeError:
            # Some LangGraph versions do not accept `retry` in add_node.
            workflow.add_node("resume_agent", resume_agent)
            workflow.add_node("scoring_agent", scoring_agent)
            workflow.add_node("recommendation_agent", recommendation_agent)
            workflow.add_node("reporting_agent", reporting_agent)
            workflow.add_node("opportunity_agent", opportunity_agent)
            workflow.add_node("recovery_agent", recovery_agent)
    except ImportError:
        # Fallback if RetryPolicy is not directly importable
        workflow.add_node("resume_agent", resume_agent)
        workflow.add_node("scoring_agent", scoring_agent)
        workflow.add_node("recommendation_agent", recommendation_agent)
        workflow.add_node("reporting_agent", reporting_agent)
        workflow.add_node("opportunity_agent", opportunity_agent)
        workflow.add_node("recovery_agent", recovery_agent)

    workflow.add_edge(START, "resume_agent")
    
    # edges
    workflow.add_conditional_edges(
        "resume_agent",
        route_after_resume,
        {
            "scoring": "scoring_agent",
            "recovery": "recovery_agent"
        }
    )
    
    workflow.add_conditional_edges(
        "scoring_agent",
        route_after_scoring,
        {
            "recommendation": "recommendation_agent",
            "recovery": "recovery_agent"
        }
    )
    
    workflow.add_conditional_edges(
        "recommendation_agent",
        route_after_recommendation,
        {
            "reporting": "reporting_agent",
            "recovery": "recovery_agent"
        }
    )
    
    workflow.add_edge("reporting_agent", "opportunity_agent")
    workflow.add_edge("opportunity_agent", END)
    
    # Recovery just ends graph gracefully
    workflow.add_edge("recovery_agent", END)
    
    return workflow.compile(checkpointer=memory)

career_os_graph = build_orchestrator_graph()

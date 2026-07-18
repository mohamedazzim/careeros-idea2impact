"""Phase 13 — Interview Graph (LangGraph).

State graph for real-time AI interview sessions with WebSocket streaming.

Flow:
  START → welcome → ask_question → listen → evaluate
  → (follow_up | next_question)
  → END

Integrates with existing LiveInterviewOrchestrator for state management
and WebSocketSessionManager for real-time event broadcasting.
"""

import logging
from langgraph.graph import StateGraph, START, END
from src.services.checkpoint import get_checkpoint_saver

from src.observability.enterprise_logging import graph_log, interview_log

logger = logging.getLogger(__name__)

_interview_graph = None


class InterviewGraphState(dict):
    """Typed state for the interview graph."""
    pass


def build_interview_graph():
    """Build and compile the LangGraph interview graph."""
    memory = get_checkpoint_saver()
    workflow = StateGraph(InterviewGraphState)

    nodes = [
        ("welcome_node", _welcome_node),
        ("ask_question_node", _ask_question_node),
        ("listen_node", _listen_node),
        ("evaluate_node", _evaluate_node),
        ("follow_up_node", _follow_up_node),
        ("closing_node", _closing_node),
    ]
    for name, func in nodes:
        workflow.add_node(name, func)

    workflow.add_edge(START, "welcome_node")
    workflow.add_edge("welcome_node", "ask_question_node")
    workflow.add_edge("ask_question_node", "listen_node")
    workflow.add_edge("listen_node", "evaluate_node")

    workflow.add_conditional_edges(
        "evaluate_node",
        _route_after_evaluation,
        {
            "follow_up": "follow_up_node",
            "next_question": "ask_question_node",
            "end": "closing_node",
        },
    )

    workflow.add_edge("follow_up_node", "ask_question_node")
    workflow.add_edge("closing_node", END)

    graph = workflow.compile(checkpointer=memory)
    graph_log.log_event(
        operation="graph_compile",
        message="Interview graph compiled",
        status="success",
        metadata={"graph": "interview_graph", "nodes": len(nodes)},
    )
    return graph


async def _welcome_node(state: InterviewGraphState) -> InterviewGraphState:
    """Deliver welcome message and initialize interview state."""
    interview_log.log_event(
        operation="graph_welcome",
        message="Interview graph: welcome node",
        metadata={"session_uid": state.get("session_uid", "")},
    )
    state["stage"] = "welcome"
    state["welcome_sent"] = True
    return state


async def _ask_question_node(state: InterviewGraphState) -> InterviewGraphState:
    """Generate and deliver the next interview question."""
    question_index = state.get("question_index", 0)
    interview_log.log_event(
        operation="graph_question",
        message=f"Asking question {question_index + 1}",
        metadata={
            "session_uid": state.get("session_uid", ""),
            "question_index": question_index,
            "total_questions": state.get("total_questions", 5),
        },
    )
    state["stage"] = "asking"
    state["awaiting_response"] = True
    return state


async def _listen_node(state: InterviewGraphState) -> InterviewGraphState:
    """Wait for user response (handled externally via WebSocket)."""
    interview_log.log_event(
        operation="graph_listen",
        message="Listening for user response",
        metadata={"session_uid": state.get("session_uid", "")},
    )
    state["stage"] = "listening"
    state["awaiting_response"] = True
    return state


async def _evaluate_node(state: InterviewGraphState) -> InterviewGraphState:
    """Evaluate user response and determine next step."""
    question_index = state.get("question_index", 0)
    total = state.get("total_questions", 5)
    scores = state.get("scores", [])
    follow_up_depth = state.get("follow_up_depth", 0)

    interview_log.log_event(
        operation="graph_evaluate",
        message="Evaluating candidate response",
        metadata={
            "session_uid": state.get("session_uid", ""),
            "question_index": question_index,
            "total": total,
            "follow_up_depth": follow_up_depth,
        },
    )

    state["stage"] = "evaluating"
    state["awaiting_response"] = False

    last_score = scores[-1] if scores else 70
    should_follow_up = last_score < 70 and follow_up_depth < 3

    state["should_follow_up"] = should_follow_up
    state["question_index"] = question_index + 1 if not should_follow_up else question_index
    return state


async def _follow_up_node(state: InterviewGraphState) -> InterviewGraphState:
    """Handle follow-up question for weak responses."""
    follow_up_depth = state.get("follow_up_depth", 0) + 1
    state["follow_up_depth"] = follow_up_depth
    interview_log.log_event(
        operation="graph_follow_up",
        message=f"Follow-up question depth {follow_up_depth}",
        metadata={
            "session_uid": state.get("session_uid", ""),
            "follow_up_depth": follow_up_depth,
        },
    )
    state["stage"] = "follow_up"
    return state


async def _closing_node(state: InterviewGraphState) -> InterviewGraphState:
    """Close the interview and compute final scores."""
    interview_log.log_event(
        operation="graph_closing",
        message="Closing interview session",
        metadata={
            "session_uid": state.get("session_uid", ""),
            "total_questions": state.get("question_index", 0),
        },
    )
    state["stage"] = "completed"
    state["completed"] = True
    return state


def _route_after_evaluation(state: InterviewGraphState) -> str:
    """Route to follow_up, next_question, or end based on state."""
    question_index = state.get("question_index", 0)
    total = state.get("total_questions", 5)
    should_follow_up = state.get("should_follow_up", False)

    if state.get("completed"):
        return "end"
    if should_follow_up:
        return "follow_up"
    if question_index >= total:
        return "end"
    return "next_question"


def get_interview_graph():
    """Get or compile the interview graph singleton."""
    global _interview_graph
    if _interview_graph is None:
        _interview_graph = build_interview_graph()
    return _interview_graph


def reset_interview_graph() -> None:
    global _interview_graph
    _interview_graph = None

"""Interview graph tests — compilation, node execution, routing."""
import pytest


class TestInterviewGraph:
    def test_graph_compilation(self):
        from src.graphs.interview_graph import build_interview_graph
        graph = build_interview_graph()
        assert graph is not None

    def test_graph_singleton(self):
        from src.graphs.interview_graph import get_interview_graph, reset_interview_graph
        reset_interview_graph()
        g1 = get_interview_graph()
        g2 = get_interview_graph()
        assert g1 is g2

    def test_routing_ends_at_total_questions(self):
        from src.graphs.interview_graph import _route_after_evaluation, InterviewGraphState
        state = InterviewGraphState({
            "question_index": 5,
            "total_questions": 5,
            "should_follow_up": False,
            "completed": True,
        })
        route = _route_after_evaluation(state)
        assert route == "end"

    def test_routing_follow_up(self):
        from src.graphs.interview_graph import _route_after_evaluation, InterviewGraphState
        state = InterviewGraphState({
            "question_index": 2,
            "total_questions": 5,
            "should_follow_up": True,
            "completed": False,
        })
        route = _route_after_evaluation(state)
        assert route == "follow_up"

    def test_routing_next_question(self):
        from src.graphs.interview_graph import _route_after_evaluation, InterviewGraphState
        state = InterviewGraphState({
            "question_index": 3,
            "total_questions": 5,
            "should_follow_up": False,
            "completed": False,
        })
        route = _route_after_evaluation(state)
        assert route == "next_question"

    @pytest.mark.asyncio
    async def test_welcome_node(self):
        from src.graphs.interview_graph import _welcome_node, InterviewGraphState
        state = InterviewGraphState({})
        result = await _welcome_node(state)
        assert result["stage"] == "welcome"
        assert result["welcome_sent"] is True

    @pytest.mark.asyncio
    async def test_closing_node(self):
        from src.graphs.interview_graph import _closing_node, InterviewGraphState
        state = InterviewGraphState({"question_index": 5})
        result = await _closing_node(state)
        assert result["stage"] == "completed"
        assert result["completed"] is True

import pytest
import time
from src.schemas.orchestration import CareerOSState

pytestmark = pytest.mark.skip(reason="Orchestration tests require running Qdrant server")

from src.services.orchestration.graph import career_os_graph

@pytest.mark.asyncio
async def test_end_to_end_graph(monkeypatch):
    monkeypatch.setenv("MOCK_RETRIEVAL_AGENT", "true")
    monkeypatch.setenv("MOCK_EVAL", "true")
    
    initial_state = {
        "user_id": "u_1",
        "resume_id": "r_1",
        "job_id": "j_1",
        "errors": [],
        "metadata": {},
        "execution_metrics": {},
        "timestamp": time.time(),
        "graph_version": "v1",
        "retries": {}
    }
    
    config = {"configurable": {"thread_id": "test_thread_1"}}
    
    final_state = await career_os_graph.ainvoke(initial_state, config=config)
    
    # Assertions
    assert len(final_state["errors"]) == 0
    assert "evaluation_result" in final_state
    assert final_state["opportunity_alert"] in [True, False]
    assert "report" in final_state
    assert final_state["report"]["status"] == "completed"

@pytest.mark.asyncio
async def test_recovery_flow(monkeypatch):
    monkeypatch.setenv("MOCK_RETRIEVAL_AGENT", "true")
    
    # Force scoring to fail by returning an invalid/empty eval response from mock?
    # Or just inject an error manually. We can mock the scoring_agent easily but the graph is compiled.
    # We can inject an error during resume_agent manually. 
    # Just set a bad state that causes the resume agent to fail. Wait, the resume_agent catches exceptions and adds to errors.
    # Let's mock a component raising an exception.
    
    initial_state = {
        "user_id": "u_1",
        "resume_id": "r_1",
        "job_id": "j_1",
        "errors": ["Forced Error"],  # Start out with an error
        "metadata": {},
        "execution_metrics": {},
        "timestamp": time.time(),
        "graph_version": "v1",
        "retries": {}
    }
    
    config = {"configurable": {"thread_id": "test_thread_2"}}
    
    final_state = await career_os_graph.ainvoke(initial_state, config=config)
    
    # The graph will start at resume_agent, resume_agent will run (does not block on previous errors), 
    # but the conditional edge after resume_agent routes to 'recovery' if state['errors'] is not empty.
    # Let's check if it hit recovery.
    assert "failed_with_recovery" == final_state.get("metadata", {}).get("status")

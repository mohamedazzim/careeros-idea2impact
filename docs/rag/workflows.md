# Workflows and End-to-End Behavior

Last verified from source code: 2026-06-14

## LangGraph modules

- `backend/src/graphs/opportunity_graph.py`
- `backend/src/graphs/interview_graph.py`
- `backend/src/graphs/outcome_intelligence_graph.py`

## Opportunity graph

Main flow:

1. `retrieve_candidate_context`
2. `retrieve_market_context`
3. `evaluate_opportunity_fit`
4. `evaluate_urgency`
5. `generate_priority_score`
6. `governance_validation`
7. `notification_decision`
8. `voice_synthesis` or trace compilation
9. `twilio_call_execution` when voice delivery is approved
10. `trace_compilation`

## Interview graph

Main flow:

1. `welcome_node`
2. `ask_question_node`
3. `listen_node`
4. `evaluate_node`
5. Conditional routing
6. `closing_node`

## Outcome intelligence graph

Main flow:

1. `conversation_retrieval`
2. `outcome_classification`
3. `concern_extraction`
4. `memory_update`
5. `persistence`

## Source anchors

- `backend/src/graphs/opportunity_graph.py`
- `backend/src/graphs/interview_graph.py`
- `backend/src/graphs/outcome_intelligence_graph.py`
- `backend/src/services/orchestration/graph.py`
- `backend/src/services/opportunity/communication_orchestrator.py`
- `backend/src/services/opportunity/conversational_outbound_call_service.py`

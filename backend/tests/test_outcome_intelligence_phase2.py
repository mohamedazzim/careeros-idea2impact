from src.services.opportunity.communication_orchestrator import CommunicationOrchestrator
from src.services.opportunity.conversation_retrieval_agent import ConversationRetrievalAgent
from src.services.opportunity.outcome_intelligence_agent import OutcomeIntelligenceAgent


def test_transcript_turn_normalization():
    payload = {"transcript": [{"role": "agent", "message": "Hello"}, {"role": "user", "message": "I am interested"}]}
    assert ConversationRetrievalAgent._speaker_turns(payload) == [
        {"speaker": "agent", "text": "Hello"}, {"speaker": "user", "text": "I am interested"}
    ]


def test_deterministic_interested_classification():
    outcome = OutcomeIntelligenceAgent._deterministic_fallback("User: I am interested, tell me more about remote work")
    assert outcome.outcome == "INTERESTED"
    assert outcome.interest_level == "HIGH"
    assert outcome.primary_concern == "REMOTE_PREFERENCE"


def test_deterministic_not_interested_classification():
    outcome = OutcomeIntelligenceAgent._deterministic_fallback("User: No thanks, I am not interested")
    assert outcome.outcome == "NOT_INTERESTED"
    assert outcome.followup_required is False


def test_nested_provider_identifier_extraction():
    payload = {"body": {"data": {"conversation_id": "conv-123", "agent_id": "agent-1"}}}
    assert CommunicationOrchestrator._find_provider_value("conversation_id", payload) == "conv-123"
    assert CommunicationOrchestrator._find_provider_value("agent_id", payload) == "agent-1"

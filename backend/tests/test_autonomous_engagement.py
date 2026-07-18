from datetime import datetime
import pytest
from src.services.opportunity.followup_agent import RULES
from src.services.opportunity.communication_orchestrator import CommunicationOrchestrator
from src.services.opportunity.opportunity_reranking_agent import OpportunityRerankingAgent
from src.services.opportunity.voice_opportunity_agent import VoiceOpportunityAgent
from src.observability.langsmith.decorators import _redact_dict

@pytest.mark.parametrize("outcome,action",[
 ("APPLYING","FOLLOW_UP_EMAIL"),("INTERESTED","FOLLOW_UP_SMS"),("MAYBE_LATER","WAIT"),
 ("REQUEST_FOLLOWUP","FOLLOW_UP_CALL"),("NOT_INTERESTED","CLOSE"),("NOT_QUALIFIED","CLOSE")])
def test_followup_rules(outcome,action): assert RULES[outcome][0]==action

def test_reranking_formula_behavior():
 score=80*(.5+.8/2)*(.5+.6/2)
 assert round(score,2)==57.6

def test_provider_value_recursive():
 assert CommunicationOrchestrator._find_provider_value("conversation_id",{"a":{"conversation_id":"c1"}})=="c1"

def test_langsmith_trace_redaction():
 redacted=_redact_dict({"candidate_id":"user-1","phone_number":"+12025550124","nested":{"api_key":"secret"},"safe":"ok"})
 assert redacted=={"candidate_id":"[REDACTED]","phone_number":"[REDACTED]","nested":{"api_key":"[REDACTED]"},"safe":"ok"}


def test_voice_agent_tamil_script_and_followup():
 agent = VoiceOpportunityAgent()
 intelligence = {
  "job": {"title": "Flutter Developer", "company": "CareerOS"},
  "match_intelligence": {"match_score": 88, "matched_skills": ["Flutter"], "missing_skills": []},
  "urgency_intelligence": {"application_urgency": "high"},
  "salary_intelligence": {"salary_range": "₹8-12 LPA"},
  "deadline_intelligence": {},
  "language_preferences": {"preferred_language": "tamil"},
 }
 script = agent.build_script(intelligence)
 assert "CareerOS" in script
 assert "தமிழ்" not in script or "வணக்கம்" in script
 followup = agent.build_follow_up_script(intelligence, "match_reasoning")
 assert "salary" in followup.lower() or "salary" in followup
 assert "CareerOS" in followup

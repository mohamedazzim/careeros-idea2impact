"""Phase 5 — Opportunity Scoring Agent.

Scores opportunities across 11 weighted dimensions with evidence citations
and confidence calibration. Rule-based for data-driven dimensions (skills),
LLM-powered for qualitative dimensions via the shared provider abstraction.
"""

import time
import uuid
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.agents.agent_observability import get_agent_observability


@dataclass
class ScoringState:
    scoring_run_id: str
    user_id: str
    opportunity_id: str
    overall_score: float = 0.0
    confidence: float = 0.5
    dimension_scores: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    evidence_citations: List[Dict[str, str]] = field(default_factory=list)
    reasoning_chain: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    status: str = "active"


class OpportunityScoringAgent:
    AGENT_NAME = "opportunity_scoring"

    WEIGHTS = settings.OPPORTUNITY_MATCH_WEIGHTS
    DATA_DIMENSIONS = {"ats_fit", "skill_overlap", "missing_skills"}
    LLM_DIMENSIONS = {
        "seniority_fit", "compensation_relevance", "role_alignment",
        "domain_alignment", "application_urgency", "market_demand",
    }

    ALL_DIMENSIONS = [
        "ats_fit", "skill_overlap", "missing_skills", "seniority_fit",
        "compensation_relevance", "role_alignment", "domain_alignment",
        "application_urgency", "market_demand",
    ]

    def __init__(self):
        self.observability = get_agent_observability()

    async def score(
        self, user_id: str, opportunity: Dict[str, Any], candidate_context: Optional[Dict[str, Any]] = None
    ) -> ScoringState:
        t0 = time.time()
        state = ScoringState(
            scoring_run_id=str(uuid.uuid4()),
            user_id=user_id,
            opportunity_id=opportunity.get("id", ""),
        )

        try:
            candidate = candidate_context or {}

            # ── Data-driven dimensions (rule-based) ──
            for dim in self.DATA_DIMENSIONS:
                dim_result = await self._score_dimension_rule(dim, opportunity, candidate)
                state.dimension_scores[dim] = dim_result
                state.evidence_citations.extend(dim_result.get("citations", []))
                state.reasoning_chain.append(f"{dim}: {dim_result['score']}/100 (confidence: {dim_result['confidence']})")

            # ── Qualitative dimensions (LLM-powered) ──
            llm_results = await self._score_dimensions_llm(opportunity, candidate)
            for dim in self.LLM_DIMENSIONS:
                dim_result = llm_results.get(dim, {"score": 50, "confidence": 0.3, "citations": []})
                state.dimension_scores[dim] = dim_result
                state.evidence_citations.extend(dim_result.get("citations", []))
                state.reasoning_chain.append(f"{dim}: {dim_result['score']}/100 (confidence: {dim_result['confidence']})")

            state.overall_score = self._weighted_aggregate(state.dimension_scores)
            state.confidence = self._compute_confidence(state)
            state.status = "completed"
            self.observability.record_agent_execution(self.AGENT_NAME, "completed")
        except Exception as exc:
            state.errors.append(str(exc))
            state.status = "failed"
            self.observability.record_agent_execution(self.AGENT_NAME, "failed")

        self.observability.record_agent_latency(self.AGENT_NAME, time.time() - t0)
        self.observability.record_confidence(self.AGENT_NAME, state.confidence)
        return state

    async def _score_dimension_rule(
        self, dim: str, opportunity: Dict[str, Any], candidate: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rule-based scoring for data-driven dimensions (skill overlap, ATS fit, missing skills)."""
        skills = [s.lower() for s in opportunity.get("skills", [])]
        candidate_skills = [s.lower() for s in candidate.get("skills", [])]
        matched = set(skills) & set(candidate_skills)
        missing = set(skills) - set(candidate_skills)

        if dim == "ats_fit":
            score = min(100, len(matched) * 25) if skills else 50
            return {"score": score, "confidence": 0.7, "citations": [{"match": m} for m in list(matched)[:3]]}
        if dim == "skill_overlap":
            ratio = len(matched) / max(len(skills), 1)
            return {"score": int(ratio * 100), "confidence": 0.8, "citations": [{"matched_skill": m} for m in list(matched)[:3]]}
        if dim == "missing_skills":
            penalty = len(missing) * 15
            return {"score": max(0, 100 - penalty), "confidence": 0.7, "citations": [{"missing": m} for m in list(missing)[:3]]}
        return {"score": 0, "confidence": 0.0, "citations": []}

    async def _score_dimensions_llm(
        self, opportunity: Dict[str, Any], candidate: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """Use ClaudeService to score qualitative dimensions."""
        from src.services.intelligence.claude_service import get_claude_service

        title = opportunity.get("title", "")
        company = opportunity.get("company", "")
        opp_text = opportunity.get("text", "")[:2000]
        opp_skills = opportunity.get("skills", [])

        candidate_skills = candidate.get("skills", [])
        candidate_titles = candidate.get("titles", [])
        target_role = candidate.get("target_role", "")
        experience_years = candidate.get("experience_years", 0)

        system_prompt = (
            "You are an expert job matching evaluator. Score each dimension 0-100 "
            "with a confidence 0.0-1.0 and 1-3 evidence citations. "
            "Return valid JSON with keys: seniority_fit, compensation_relevance, "
            "role_alignment, domain_alignment, application_urgency, "
            "market_demand. Each value is {score: int, confidence: float, citations: [string]}."
        )

        human_message = (
            f"Opportunity: {title} at {company}\n"
            f"Description: {opp_text[:800]}\n"
            f"Required skills: {', '.join(opp_skills[:10])}\n\n"
            f"Candidate skills: {', '.join(candidate_skills[:10])}\n"
            f"Candidate titles: {', '.join(candidate_titles[:5])}\n"
            f"Target role: {target_role}\n"
            f"Experience years: {experience_years}\n\n"
            "Score each dimension considering the candidate profile vs opportunity requirements. "
            "Return JSON only."
        )

        try:
            claude = get_claude_service()
            response = await claude.reason_text(
                system_prompt=system_prompt,
                human_message=human_message,
                category="evaluation",
            )

            result_text = response.get("result", "")
            if hasattr(result_text, "content"):
                result_text = result_text.content

            # Parse JSON from LLM response
            if isinstance(result_text, str):
                # Strip markdown code fences if present
                cleaned = result_text.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                parsed = json.loads(cleaned)
            elif isinstance(result_text, dict):
                parsed = result_text
            else:
                return self._fallback_llm_scores()

            # Validate and normalise
            llm_scores = {}
            for dim in self.LLM_DIMENSIONS:
                entry = parsed.get(dim, {})
                if isinstance(entry, dict):
                    llm_scores[dim] = {
                        "score": max(0, min(100, int(entry.get("score", 50)))),
                        "confidence": max(0.0, min(1.0, float(entry.get("confidence", 0.3)))),
                        "citations": entry.get("citations", [])[:3],
                    }
                else:
                    llm_scores[dim] = {"score": 50, "confidence": 0.3, "citations": []}
            return llm_scores

        except Exception:
            self.observability.record_agent_execution(f"{self.AGENT_NAME}_llm", "failed")
            return self._fallback_llm_scores()

    def _fallback_llm_scores(self) -> Dict[str, Dict[str, Any]]:
        """Graceful degradation when LLM is unavailable."""
        return {
            "seniority_fit": {"score": 60, "confidence": 0.5, "citations": []},
            "compensation_relevance": {"score": 50, "confidence": 0.3, "citations": []},
            "role_alignment": {"score": 55, "confidence": 0.4, "citations": []},
            "domain_alignment": {"score": 55, "confidence": 0.4, "citations": []},
            "application_urgency": {"score": 30, "confidence": 0.5, "citations": []},
            "market_demand": {"score": 60, "confidence": 0.4, "citations": []},
        }

    def _weighted_aggregate(self, scores: Dict[str, Dict[str, Any]]) -> float:
        total = 0.0
        for dim, info in scores.items():
            weight = self.WEIGHTS.get(dim, 0.05)
            total += info["score"] * weight
        return round(total, 1)

    def _compute_confidence(self, state: ScoringState) -> float:
        confidences = [d["confidence"] for d in state.dimension_scores.values()]
        if not confidences:
            return 0.5
        return round(sum(confidences) / len(confidences), 2)


# ── Singleton ────────────────────────────────────────────────────────

_agent: Optional[OpportunityScoringAgent] = None


def get_opportunity_scoring_agent() -> OpportunityScoringAgent:
    global _agent
    if _agent is None:
        _agent = OpportunityScoringAgent()
    return _agent


def reset_opportunity_scoring_agent() -> None:
    global _agent
    _agent = None

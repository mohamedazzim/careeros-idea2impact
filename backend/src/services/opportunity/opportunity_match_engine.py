"""Phase 5 — Opportunity Match Engine.

Multi-dimensional scoring across 10 dimensions with weighted aggregation.
All scores are evidenced and explainable.
"""

from typing import Any, Dict, Optional

from src.core.config import settings
from src.services.intelligence.career_domain_classifier import get_career_domain_classifier


class OpportunityMatchEngine:

    WEIGHTS = settings.OPPORTUNITY_MATCH_WEIGHTS
    DIMENSIONS = [
        "ats_fit", "skill_overlap", "missing_skills", "seniority_fit",
        "compensation_relevance", "role_alignment", "domain_alignment",
        "application_urgency", "posted_within_32_hours", "market_demand",
    ]

    def score(
        self,
        opportunity: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        dimension_scores = {}
        evidence = []

        # Pre-filter: Check domain alignment before scoring
        classifier = get_career_domain_classifier()
        job_classification = classifier.classify_job(
            opportunity.get("title", ""),
            opportunity.get("description", ""),
            opportunity.get("skills", []),
        )
        resume_classification = classifier.classify_resume(
            candidate.get("resume_text", ""),
            candidate.get("skills", []),
            candidate.get("target_role", ""),
        )

        domain_score, domain_reason = classifier.calculate_domain_alignment(
            resume_classification["career_family"],
            job_classification["career_family"],
        )

        # If completely unrelated domain, return low score immediately
        if domain_score == 0:
            return {
                "overall_score": 15.0,
                "confidence": 0.85,
                "dimension_scores": {
                    "domain_alignment": {
                        "score": 0,
                        "confidence": 0.90,
                        "citations": [{
                            "reason": domain_reason,
                            "resume_family": resume_classification["career_family"],
                            "job_family": job_classification["career_family"],
                            "resume_display": resume_classification["family_display"],
                            "job_display": job_classification["family_display"],
                        }],
                        "weight": 0.30,
                    },
                },
                "weights": dict(self.WEIGHTS),
                "evidence_citations": [{
                    "type": "domain_mismatch",
                    "resume_family": resume_classification["career_family"],
                    "job_family": job_classification["career_family"],
                    "resume_display": resume_classification["family_display"],
                    "job_display": job_classification["family_display"],
                }],
                "opportunity_id": opportunity.get("id", ""),
                "domain_filtered": True,
                "domain_alignment": domain_score,
                "domain_reason": domain_reason,
            }

        for dim in self.DIMENSIONS:
            result = self._score_dimension(dim, opportunity, candidate)
            dimension_scores[dim] = {
                "score": result[0],
                "confidence": result[1],
                "citations": result[2],
                "weight": self.WEIGHTS.get(dim, 0.05),
            }
            evidence.extend(result[2])

        # Override domain_alignment with our classifier score
        dimension_scores["domain_alignment"] = {
            "score": domain_score,
            "confidence": 0.90,
            "citations": [{
                "reason": domain_reason,
                "resume_family": resume_classification["career_family"],
                "job_family": job_classification["career_family"],
            }],
            "weight": self.WEIGHTS.get("domain_alignment", 0.05),
        }

        overall = self._aggregate(dimension_scores)
        confidence = self._overall_confidence(dimension_scores)

        return {
            "overall_score": overall,
            "confidence": confidence,
            "dimension_scores": dimension_scores,
            "weights": dict(self.WEIGHTS),
            "evidence_citations": evidence,
            "opportunity_id": opportunity.get("id", ""),
            "domain_alignment": domain_score,
            "domain_reason": domain_reason,
            "job_family": job_classification["career_family"],
            "resume_family": resume_classification["career_family"],
        }

    def _score_dimension(
        self, dim: str, opp: Dict[str, Any], candidate: Dict[str, Any]
    ) -> tuple:
        skills = [s.lower() for s in opp.get("skills", [])]
        candidate_skills = [s.lower() for s in candidate.get("skills", [])]
        matched = set(skills) & set(candidate_skills)
        missing = set(skills) - set(candidate_skills)
        title = opp.get("title", "").lower()
        target_role = candidate.get("target_role", "").lower()

        if dim == "ats_fit":
            score = min(100, len(matched) * 25) if skills else 50
            cites = [{"skill": s, "match": "ats_keyword"} for s in list(matched)[:3]]
            return score, 0.75, cites

        if dim == "skill_overlap":
            ratio = len(matched) / max(len(skills), 1)
            return int(ratio * 100), 0.80, [{"matched": s} for s in list(matched)[:3]]

        if dim == "missing_skills":
            penalty = min(100, len(missing) * 18)
            return max(0, 100 - penalty), 0.70, [{"gap": s} for s in list(missing)[:3]]

        if dim == "seniority_fit":
            levels = {"junior": 0.2, "mid": 0.4, "senior": 0.7, "staff": 0.85, "lead": 0.9, "principal": 0.95}
            for lvl, score_base in levels.items():
                if lvl in title:
                    return int(score_base * 100), 0.55, [{"level": lvl}]
            return 55, 0.45, []

        if dim == "role_alignment":
            if target_role and target_role in title:
                return 85, 0.65, [{"target_role": target_role}]
            return 45, 0.30, []

        if dim == "compensation_relevance":
            salary_range = opp.get("salary_range", "")
            candidate_salary = candidate.get("target_salary", "")
            if salary_range and candidate_salary:
                try:
                    opp_low = float(salary_range.replace("$","").replace(",","").split("-")[0])
                    cand = float(str(candidate_salary).replace("$","").replace(",",""))
                    ratio = cand / max(opp_low, 1)
                    if 0.8 <= ratio <= 1.3:
                        return 85, 0.65, [{"salary_alignment": "within_range"}]
                    elif ratio < 0.8:
                        return 45, 0.65, [{"salary_alignment": "below_range"}]
                    else:
                        return 30, 0.65, [{"salary_alignment": "above_range"}]
                except (ValueError, TypeError, AttributeError):
                    pass
            if salary_range:
                return 65, 0.45, [{"salary_range": salary_range}]
            return 50, 0.30, [{"note": "compensation data not available"}]

        if dim == "domain_alignment":
            # Domain alignment is now handled by the pre-filter above
            # This is a fallback for when the pre-filter doesn't catch it
            domains = candidate.get("domains", [])
            opp_domain = opp.get("domain", "")
            if opp_domain and opp_domain.lower() in [d.lower() for d in domains]:
                return 80, 0.50, [{"domain": opp_domain}]
            return 50, 0.30, []

        if dim == "application_urgency":
            urgency_keywords = ["urgent", "immediate", "asap", "closing", "immediate hire"]
            title_and_desc = title + " " + (opp.get("description", "") or "")[:200].lower()
            hits = sum(1 for kw in urgency_keywords if kw in title_and_desc)
            return min(100, hits * 25 + 20), 0.40, [{"keywords_found": hits}]

        if dim == "posted_within_32_hours":
            if deadline := opp.get("deadline"):
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
                    days = (dt - datetime.utcnow()).days
                    if days <= 0:
                        return 100, 0.70, []
                    if days <= 1:
                        return 90, 0.70, [{"days_remaining": days}]
                except (ValueError, TypeError):
                    pass
            return 30, 0.30, [{"note": "no deadline found"}]

        if dim == "market_demand":
            signals = opp.get("market_signals", {})
            if signals:
                demand_score = float(signals.get("demand_score", 55))
                return min(100, max(20, demand_score)), 0.55, signals.get("citations", [{"source": "market_signals"}])[:3]
            title_demand_keywords = ["senior", "staff", "lead", "principal", "architect", "urgent"]
            hits = sum(1 for kw in title_demand_keywords if kw in title)
            return min(100, 40 + hits * 15), 0.40, [{"demand_indicators": hits}]

        return 0, 0.0, []

    def _aggregate(self, dimension_scores: Dict[str, Any]) -> float:
        total = 0.0
        for dim, info in dimension_scores.items():
            weight = info.get("weight", 0.05)
            total += info["score"] * weight
        return round(total, 1)

    def _overall_confidence(self, dimension_scores: Dict[str, Any]) -> float:
        confidences = [info["confidence"] for info in dimension_scores.values()]
        return round(sum(confidences) / max(len(confidences), 1), 2) if confidences else 0.5


_engine: Optional[OpportunityMatchEngine] = None

def get_opportunity_match_engine() -> OpportunityMatchEngine:
    global _engine
    if _engine is None:
        _engine = OpportunityMatchEngine()
    return _engine

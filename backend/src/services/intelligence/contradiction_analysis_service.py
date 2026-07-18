"""
Contradiction analysis — detects contradictory signals in resumes and evaluations.

Identifies contradictory experience, seniority, skill evidence,
inconsistent chronology, and inflated achievement claims.

Stateless, async-safe, observable.
"""
import logging
import re
from typing import Dict, Any, List, Optional
from src.observability.metrics import (
    RETRIEVAL_CONSISTENCY,
    HALLUCINATION_RISK_SCORE,
)

logger = logging.getLogger(__name__)


class ContradictionAnalyzer:
    """Enterprise contradiction detection for resume and evaluation signals."""

    def analyze(
        self,
        resume_text: str,
        job_text: str = "",
        ats_data: Optional[Dict[str, Any]] = None,
        skill_gaps: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Full contradiction analysis across all signals.

        Returns contradiction report with severity and affected categories.
        """
        resume_lower = resume_text.lower()
        job_lower = job_text.lower()

        contradictions = []

        # 1. Contradictory experience signals
        exp_contradictions = self._detect_experience_contradictions(resume_text, job_text)
        if exp_contradictions:
            contradictions.append({"category": "experience", "signals": exp_contradictions})

        # 2. Contradictory seniority indicators
        sen_contradictions = self._detect_seniority_contradictions(resume_text, job_text)
        if sen_contradictions:
            contradictions.append({"category": "seniority", "signals": sen_contradictions})

        # 3. Contradictory skill evidence
        skill_contradictions = self._detect_skill_contradictions(resume_text, job_text, skill_gaps)
        if skill_contradictions:
            contradictions.append({"category": "skills", "signals": skill_contradictions})

        # 4. Inconsistent chronology
        chrono = self._detect_chronology_inconsistency(resume_text)
        if chrono:
            contradictions.append({"category": "chronology", "signals": chrono})

        # 5. Inflated achievement claims
        inflated = self._detect_inflated_claims(resume_text)
        if inflated:
            contradictions.append({"category": "inflated_claims", "signals": inflated})

        # 6. ATS vs skill-gap contradiction
        ats_vs_gap = self._detect_ats_gap_contradictions(ats_data, skill_gaps)
        if ats_vs_gap:
            contradictions.append({"category": "ats_vs_skills", "signals": ats_vs_gap})

        total_signals = sum(len(c["signals"]) for c in contradictions)
        severity = (
            "critical" if total_signals >= 5 else
            "high" if total_signals >= 3 else
            "medium" if total_signals >= 1 else "none"
        )

        consistency_score = max(0.0, 1.0 - (total_signals * 0.15))
        RETRIEVAL_CONSISTENCY.observe(consistency_score)
        if severity != "none":
            HALLUCINATION_RISK_SCORE.observe(min(1.0, total_signals * 0.1))

        return {
            "contradictions_detected": len(contradictions) > 0,
            "total_signals": total_signals,
            "severity": severity,
            "contradictions": contradictions,
            "consistency_score": round(consistency_score, 4),
            "recommendation": (
                "Multiple inconsistencies detected — evaluate evidence carefully"
                if contradictions else "No contradictions detected"
            ),
        }

    def _detect_experience_contradictions(
        self, resume: str, job: str
    ) -> List[Dict[str, str]]:
        signals = []
        # Junior title vs senior years
        if re.search(r"(?i)\bjunior\b", resume) and re.search(r"\b(?:10|15|20)\+\s*years\b", resume):
            signals.append({"type": "junior_title_senior_years", "detail": "Junior title with 10+ years claimed"})
        # Job requires senior experience but resume shows entry-level
        if re.search(r"(?i)(?:10\+|10\s*or\s*more|senior\s*level|principal)", job):
            if re.search(r"(?i)\b(?:intern|junior|entry.level)\b", resume):
                signals.append({"type": "entry_level_vs_senior_role", "detail": "Entry-level signals vs senior job requirement"})
        return signals

    def _detect_seniority_contradictions(
        self, resume: str, job: str
    ) -> List[Dict[str, str]]:
        signals = []
        years = re.findall(r"\b(\d+)\+?\s*(?:years|yrs)", resume.lower())
        if years:
            max_years = max(int(y) for y in years)
            if max_years > 5 and re.search(r"(?i)\b(?:junior|associate|entry.level)\b", resume):
                signals.append({"type": "years_vs_title", "detail": f"Claims {max_years}+ years with junior/associate title"})
        return signals

    def _detect_skill_contradictions(
        self, resume: str, job: str, skill_gaps: Optional[Dict]
    ) -> List[Dict[str, str]]:
        signals = []
        if not skill_gaps:
            return signals
        gaps_data = skill_gaps.get("data", skill_gaps)
        missing = gaps_data.get("missing_skills", []) if isinstance(gaps_data, dict) else []
        resume_claims = gaps_data.get("skills_found", []) if isinstance(gaps_data, dict) else []
        claimed = set(str(s).lower() for s in resume_claims)
        missing_set = set(str(m).lower() for m in missing)
        for skill in claimed & missing_set:
            signals.append({"type": "claimed_and_missing", "detail": f"'{skill}' found in resume but reported as gap"})
        return signals

    def _detect_chronology_inconsistency(self, resume: str) -> List[Dict[str, str]]:
        signals = []
        dates = re.findall(r"\b(20\d{2})\b", resume)
        if len(dates) >= 2:
            years = sorted(set(int(d) for d in dates))
            if years[-1] - years[0] > 20:
                signals.append({"type": "long_timeline", "detail": f"Timeline spans {years[-1] - years[0]} years — verify consistency"})
        return signals

    def _detect_inflated_claims(self, resume: str) -> List[Dict[str, str]]:
        signals = []
        large_percentages = re.findall(r"\b(\d{2,3})\s*%", resume)
        for pct in large_percentages:
            val = int(pct)
            if val > 90:
                signals.append({"type": "suspicious_metric", "detail": f"Claimed {val}% improvement — verify with context"})
        if len(large_percentages) > 5:
            signals.append({"type": "metric_overload", "detail": f"{len(large_percentages)} percentage metrics — potential inflation"})
        return signals

    def _detect_ats_gap_contradictions(
        self, ats_data: Optional[Dict], skill_gaps: Optional[Dict]
    ) -> List[Dict[str, str]]:
        signals = []
        if not ats_data or not skill_gaps:
            return signals
        ats_strengths = set(str(s).lower() for s in (ats_data.get("strengths", []) or []))
        gaps_missing = set()
        if isinstance(skill_gaps, dict):
            gaps = skill_gaps.get("data", skill_gaps)
            if isinstance(gaps, dict):
                gaps_missing = set(str(m).lower() for m in (gaps.get("missing_skills", []) or []))
        for skill in ats_strengths & gaps_missing:
            signals.append({"type": "strength_vs_gap", "detail": f"'{skill}' rated as strength but listed as skill gap"})
        return signals


_analyzer: Optional[ContradictionAnalyzer] = None
def get_contradiction_analyzer() -> ContradictionAnalyzer:
    global _analyzer
    if _analyzer is None: _analyzer = ContradictionAnalyzer()
    return _analyzer
def __getattr__(name: str):
    if name == "contradiction_analyzer": return get_contradiction_analyzer()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Deterministic JD-aware alignment scoring and evidence extraction.

This layer explains the RAG alignment result in human terms. It does not call
an LLM; it converts resume and JD evidence into weighted score components that
the UI can display and auditors can reproduce.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class DimensionSpec:
    key: str
    label: str
    weight: float


DIMENSIONS: List[DimensionSpec] = [
    DimensionSpec("education", "Education Match", 20.0),
    DimensionSpec("skills", "Skills and Tool Match", 25.0),
    DimensionSpec("projects", "Projects Match", 15.0),
    DimensionSpec("experience", "Experience Match", 15.0),
    DimensionSpec("certifications", "Certification Match", 10.0),
    DimensionSpec("location", "Location and Relocation Match", 5.0),
    DimensionSpec("ai_ml", "AI/ML Alignment", 5.0),
    DimensionSpec("communication", "Communication Indicators", 5.0),
]


SKILL_ALIASES: Dict[str, List[str]] = {
    "sql": ["sql", "mysql", "postgresql", "sqlite"],
    "python": ["python"],
    "power bi": ["power bi", "powerbi"],
    "ai/ml": ["ai/ml", "ai ml", "machine learning", "artificial intelligence", "ml", "ai"],
    "tensorflow": ["tensorflow"],
    "pytorch": ["pytorch"],
    "scikit-learn": ["scikit-learn", "scikit learn", "sklearn"],
    "matplotlib": ["matplotlib"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "nlp": ["nlp", "natural language processing"],
}


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _contains_any(text: str, aliases: Iterable[str]) -> bool:
    text_l = _normalize(text)
    for alias in aliases:
        pattern = r"(?<![a-z0-9])" + re.escape(alias.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, text_l):
            return True
    return False


def _extract_required_skills(jd_text: str) -> List[str]:
    jd_l = _normalize(jd_text)
    found = []
    for skill, aliases in SKILL_ALIASES.items():
        if _contains_any(jd_l, aliases):
            found.append(skill)
    return found


def _score_ratio(matches: int, total: int, default: float = 50.0) -> float:
    if total <= 0:
        return default
    return round((matches / total) * 100, 1)


def _component(key: str, score: float, matched: List[str], missing: List[str], notes: List[str]) -> Dict[str, Any]:
    spec = next(d for d in DIMENSIONS if d.key == key)
    contribution = round(score * spec.weight / 100.0, 1)
    return {
        "key": spec.key,
        "label": spec.label,
        "score": round(score, 1),
        "weight": spec.weight,
        "contribution": contribution,
        "max_contribution": spec.weight,
        "matched": matched,
        "missing": missing,
        "evidence": matched + notes,
    }


class AlignmentExplainabilityService:
    """JD-aware scoring for resume alignment reports."""

    def analyze(self, resume_text: str, jd_text: str, resume_quality: Dict[str, Any] | None = None) -> Dict[str, Any]:
        resume = resume_text or ""
        jd = jd_text or ""
        resume_l = _normalize(resume)
        jd_l = _normalize(jd)
        resume_quality = resume_quality or {}

        education = self._education(resume_l, jd_l)
        skills = self._skills(resume_l, jd_l)
        projects = self._projects(resume_l, jd_l)
        experience = self._experience(resume_l, jd_l)
        certifications = self._certifications(resume_l, jd_l)
        location = self._location(resume_l, jd_l)
        ai_ml = self._ai_ml(resume_l, jd_l)
        communication = self._communication(resume_l, jd_l, resume_quality)

        components = [education, skills, projects, experience, certifications, location, ai_ml, communication]
        final_score = round(sum(c["contribution"] for c in components), 1)
        matched_items = sorted({item for c in components for item in c["matched"]})
        missing_items = sorted({item for c in components for item in c["missing"]})

        return {
            "overall_score": final_score,
            "grade": "A" if final_score >= 85 else "B" if final_score >= 70 else "C" if final_score >= 55 else "D",
            "formula": "sum(component_score * component_weight / 100)",
            "weights": {d.key: d.weight for d in DIMENSIONS},
            "components": components,
            "matched_skills": [item for item in skills["matched"] if item],
            "missing_skills": [item for item in skills["missing"] if item],
            "matched_items": matched_items,
            "missing_items": missing_items,
            "resume_overview": self._resume_overview(resume_l),
            "jd_overview": self._jd_overview(jd_l),
            "improvement_suggestions": self._suggestions(components),
            "final_recommendation": self._recommendation(final_score, components),
            "score_scenarios": self._score_scenarios(final_score, components),
        }

    def _education(self, resume: str, jd: str) -> Dict[str, Any]:
        required_degrees = ["b.tech", "be", "m.tech", "m.e", "mca"]
        matched = []
        if _contains_any(resume, ["mca"]):
            matched.append("MCA is listed in the resume")
        if _contains_any(resume, ["bca"]):
            matched.append("BCA foundation supports IT/CSE eligibility")
        if re.search(r"2024|2025|2026|present", resume):
            matched.append("Graduation window evidence appears in education dates")
        missing = []
        if not any(_contains_any(resume, [degree]) for degree in required_degrees):
            missing.append("Eligible degree not found")
        score = 90.0 if matched and not missing else 55.0
        return _component("education", score, matched, missing, [])

    def _skills(self, resume: str, jd: str) -> Dict[str, Any]:
        required = _extract_required_skills(jd)
        if not required:
            required = ["python", "sql", "power bi", "ai/ml"]
        matched = [skill for skill in required if _contains_any(resume, SKILL_ALIASES.get(skill, [skill]))]
        missing = [skill for skill in required if skill not in matched]
        score = _score_ratio(len(matched), len(required))
        return _component("skills", score, matched, missing, [])

    def _projects(self, resume: str, jd: str) -> Dict[str, Any]:
        project_markers = [
            ("AI attendance project", ["attendance", "face recognition", "opencv"]),
            ("Fake job detection project", ["fake job", "nlp", "machine learning"]),
            ("Prediction project", ["prediction", "predictive", "car price"]),
            ("AI readiness project", ["ai readiness", "governance"]),
            ("NLP chatbot project", ["chatbot", "nlp"]),
        ]
        matched = [label for label, aliases in project_markers if _contains_any(resume, aliases)]
        missing = []
        if _contains_any(jd, ["tensorflow"]) and not _contains_any(resume, ["tensorflow"]):
            missing.append("TensorFlow project evidence not found")
        if _contains_any(jd, ["pytorch"]) and not _contains_any(resume, ["pytorch"]):
            missing.append("PyTorch project evidence not found")
        score = min(100.0, 35.0 + len(matched) * 12.0 - len(missing) * 8.0)
        return _component("projects", max(0.0, score), matched, missing, [])

    def _experience(self, resume: str, jd: str) -> Dict[str, Any]:
        matched = []
        if _contains_any(resume, ["internship", "gateway software", "greensoft"]):
            matched.append("Internship experience is present")
        if _contains_any(resume, ["python", "django", "fastapi", "data analytics"]):
            matched.append("Hands-on Python/backend/data work is present")
        missing = []
        if _contains_any(jd, ["0 to 1 years", "0-1 years"]) and not matched:
            missing.append("0-1 year experience evidence is weak")
        if _contains_any(jd, ["generative ai"]) and not _contains_any(resume, ["generative ai"]):
            missing.append("Generative AI production experience not explicit")
        score = 72.0 if matched else 30.0
        if missing:
            score -= 18.0
        return _component("experience", max(0.0, score), matched, missing, [])

    def _certifications(self, resume: str, jd: str) -> Dict[str, Any]:
        matched = []
        if _contains_any(resume, ["data science and machine learning"]):
            matched.append("Data Science and Machine Learning certification")
        if _contains_any(resume, ["python programming"]):
            matched.append("Python Programming certification")
        if _contains_any(resume, ["artificial intelligence", "machine learning"]):
            matched.append("AI/ML certification evidence")
        if _contains_any(resume, ["data visualization"]):
            matched.append("Data visualization workshop")
        missing = [] if matched else ["Certified AI/Data Science course not found"]
        score = min(100.0, len(matched) * 25.0) if matched else 0.0
        return _component("certifications", score, matched, missing, [])

    def _location(self, resume: str, jd: str) -> Dict[str, Any]:
        matched = []
        missing = []
        if _contains_any(jd, ["kerala"]):
            if _contains_any(resume, ["kerala"]):
                matched.append("Kerala location mentioned")
            else:
                missing.append("Kerala location not mentioned")
        if _contains_any(jd, ["relocate", "relocation"]):
            if _contains_any(resume, ["relocate", "relocation", "willing to relocate"]):
                matched.append("Relocation willingness stated")
            else:
                missing.append("Relocation willingness not explicitly stated")
        score = 100.0 if matched and not missing else 50.0 if matched else 0.0
        return _component("location", score, matched, missing, [])

    def _ai_ml(self, resume: str, jd: str) -> Dict[str, Any]:
        required = ["machine learning", "ai", "nlp"]
        if _contains_any(jd, ["tensorflow"]):
            required.append("tensorflow")
        if _contains_any(jd, ["pytorch"]):
            required.append("pytorch")
        matched = [item for item in required if _contains_any(resume, [item])]
        missing = [item for item in required if item not in matched]
        score = _score_ratio(len(matched), len(required), default=65.0)
        return _component("ai_ml", score, matched, missing, [])

    def _communication(self, resume: str, jd: str, resume_quality: Dict[str, Any]) -> Dict[str, Any]:
        matched = []
        if _contains_any(resume, ["communication"]):
            matched.append("Communication listed as a soft skill")
        if _contains_any(resume, ["team collaboration", "collaboration"]):
            matched.append("Team collaboration listed")
        bullet_score = float(resume_quality.get("bullet_quality", {}).get("score", 0) or 0)
        missing = []
        if bullet_score < 70:
            missing.append("Impact bullets need stronger measurable outcomes")
        score = min(100.0, 40.0 + len(matched) * 25.0)
        if missing:
            score -= 20.0
        return _component("communication", max(0.0, score), matched, missing, [])

    def _resume_overview(self, resume: str) -> Dict[str, Any]:
        return {
            "education": "MCA/BCA evidence" if _contains_any(resume, ["mca", "bca"]) else "Education evidence limited",
            "location": "Kerala mentioned" if _contains_any(resume, ["kerala"]) else "Kerala not mentioned",
            "ai_ml": "AI/ML/NLP project evidence" if _contains_any(resume, ["machine learning", "nlp", "ai"]) else "AI/ML evidence limited",
            "experience": "Internship evidence" if _contains_any(resume, ["internship"]) else "Internship evidence not found",
        }

    def _jd_overview(self, jd: str) -> Dict[str, Any]:
        return {
            "required_skills": _extract_required_skills(jd),
            "location": "Kerala" if _contains_any(jd, ["kerala"]) else "Not specified",
            "experience": "0 to 1 years" if _contains_any(jd, ["0 to 1 years", "0-1 years"]) else "Not specified",
            "conversion": "Internship to full-time conversion" if _contains_any(jd, ["internship", "full time"]) else "Not specified",
        }

    def _suggestions(self, components: List[Dict[str, Any]]) -> List[str]:
        suggestions = []
        for comp in components:
            if comp["score"] < 70:
                if comp["key"] == "location":
                    suggestions.append("Add an explicit Kerala relocation or immediate-joiner statement.")
                elif comp["key"] == "skills":
                    suggestions.append("Add missing required tools directly in the skills and project sections.")
                elif comp["key"] == "ai_ml":
                    suggestions.append("Add TensorFlow/PyTorch or generative AI evidence if truthful.")
                elif comp["key"] == "experience":
                    suggestions.append("Make internship scope, dates, and AI/ML responsibilities more explicit.")
                elif comp["key"] == "communication":
                    suggestions.append("Rewrite key bullets with measurable outcomes and collaboration evidence.")
        return suggestions or ["Resume is well aligned; tailor the opening summary to this exact role."]

    def _recommendation(self, score: float, components: List[Dict[str, Any]]) -> str:
        lowest = sorted(components, key=lambda c: c["contribution"])[:3]
        focus = ", ".join(c["label"] for c in lowest)
        if score >= 70:
            return f"Apply with light tailoring. Focus on {focus} before submission."
        if score >= 55:
            return f"Potential fit, but tailor before applying. Highest leverage areas: {focus}."
        return f"Borderline fit based on explicit evidence. Improve {focus} before applying."

    def _score_scenarios(self, base: float, components: List[Dict[str, Any]]) -> Dict[str, Any]:
        by_key = {c["key"]: c for c in components}

        def raise_component(key: str, new_score: float) -> float:
            total = base - by_key[key]["contribution"]
            total += round(new_score * by_key[key]["weight"] / 100.0, 1)
            return round(min(100.0, total), 1)

        return {
            "if_missing_skills_added": raise_component("skills", 100.0),
            "if_relocation_added": raise_component("location", 100.0),
            "if_tensorflow_pytorch_projects_added": round(
                min(100.0, raise_component("projects", 95.0) + (raise_component("ai_ml", 100.0) - base)),
                1,
            ),
        }


def get_alignment_explainability_service() -> AlignmentExplainabilityService:
    return AlignmentExplainabilityService()


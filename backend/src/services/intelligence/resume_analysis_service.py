"""
Resume analysis service — bullet quality, action-verb strength,
achievement impact, formatting intelligence, resume density,
and weak wording detection.

Analyzes resume quality signals without requiring job context.

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
import logging
import re
from collections import Counter
from typing import Dict, Any, List, Optional

from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline
from src.services.retrieval.hybrid_retrieval_service import get_hybrid_retrieval_service

logger = logging.getLogger(__name__)

STRONG_ACTION_VERBS = {
    "architected", "led", "designed", "built", "implemented", "optimized",
    "reduced", "increased", "scaled", "deployed", "migrated", "automated",
    "established", "launched", "owned", "drove", "transformed", "delivered",
    "engineered", "developed", "orchestrated", "spearheaded",
}
WEAK_ACTION_VERBS = {
    "was", "were", "helped", "assisted", "participated", "involved",
    "worked on", "responsible for", "handled", "supported", "contributed",
}
WEAK_PHRASES = [
    r"responsible for", r"worked on", r"helped with", r"assisted in",
    r"participated in", r"involved in", r"part of team that",
    r"duties included", r"tasks included",
]


class ResumeAnalysisService:
    """Production resume quality analysis with local heuristics + retrieval-grounded reasoning."""

    async def analyze(
        self, resume_text: str, enable_claude: bool = True
    ) -> Dict[str, Any]:
        """Analyze resume quality across 6 dimensions.

        Returns dict with per-dimension scores, findings, and recommendations.
        """
        lines = [l.strip() for l in resume_text.split("\n") if l.strip()]
        bullets = [l for l in lines if l.startswith(("-", "•", "*", "·")) or l[0].isupper()]
        words = resume_text.split()

        # ── Local heuristic analysis ─────────────────────────────────
        bullet_analysis = self._analyze_bullets(bullets)
        action_verb_analysis = self._analyze_verbs(bullets, words)
        formatting_analysis = self._analyze_formatting(lines, resume_text)
        density_analysis = self._analyze_density(bullets, words)
        weak_wording = self._detect_weak_wording(resume_text)
        achievement_strength = self._analyze_achievement_strength(bullets)

        result = {
            "bullet_quality": bullet_analysis,
            "action_verb_analysis": action_verb_analysis,
            "formatting_intelligence": formatting_analysis,
            "resume_density": density_analysis,
            "weak_wording": weak_wording,
            "achievement_strength": achievement_strength,
            "overall_quality_score": round(
                self._compute_quality_score(
                    bullet_analysis,
                    action_verb_analysis,
                    formatting_analysis,
                    density_analysis,
                    weak_wording,
                    achievement_strength,
                ),
                1,
            ),
        }

        # ── Optional retrieval-grounded Claude reasoning ────────────
        if enable_claude:
            try:
                hybrid = get_hybrid_retrieval_service()
                retrieval = await hybrid.retrieve(
                    query=f"resume quality {resume_text[:200]}",
                    top_k=10,
                    top_n=5,
                    use_hybrid=True,
                )
                pipeline = get_reasoning_pipeline()
                claude_response = await pipeline.reason(
                    query=f"resume analysis for {resume_text[:100]}",
                    category="resume",
                    prompt_id="resume_analysis",
                    template_vars={
                        "resume_text": resume_text,
                        "context": retrieval.context,
                    },
                )
                result["claude_analysis"] = claude_response.model_dump()
                result["overall_quality_score"] = max(
                    result["overall_quality_score"],
                    claude_response.metadata.confidence_overall * 100,
                )
            except Exception as e:
                logger.warning(f"Claude resume analysis failed: {e}")

        return result

    # ── Bullet Quality ───────────────────────────────────────────────

    def _analyze_bullets(self, bullets: List[str]) -> Dict[str, Any]:
        if not bullets:
            return {"score": 0, "count": 0, "findings": ["No bullets detected"]}

        weak_count, strong_count, no_metric_count = 0, 0, 0
        for b in bullets:
            has_metric = bool(re.search(r"\b\d+[%kKmM]\b|\b\d+\s*(?:users|customers|requests|dollars|hours|days)", b))
            if not has_metric:
                no_metric_count += 1
            verb = b.lstrip("-•*· ").split()[0].lower() if b.lstrip("-•*· ").split() else ""
            if verb in STRONG_ACTION_VERBS:
                strong_count += 1
            elif verb in WEAK_ACTION_VERBS:
                weak_count += 1

        findings = []
        if no_metric_count > len(bullets) * 0.5:
            findings.append(f"{no_metric_count}/{len(bullets)} bullets lack metrics")
        if weak_count > 0:
            findings.append(f"{weak_count} bullets use weak opening verbs")

        score = max(0, 100 - (no_metric_count * 10) - (weak_count * 15))
        return {"score": max(0, score), "count": len(bullets), "strong_bullets": strong_count,
                "weak_bullets": weak_count, "bullets_without_metrics": no_metric_count, "findings": findings}

    # ── Action Verb Analysis ─────────────────────────────────────────

    def _analyze_verbs(self, bullets: List[str], words: List[str]) -> Dict[str, Any]:
        found_strong = Counter()
        found_weak = Counter()
        for b in bullets:
            verb = b.lstrip("-•*· ").split()[0].lower() if b.lstrip("-•*· ").split() else ""
            if verb in STRONG_ACTION_VERBS:
                found_strong[verb] += 1
            elif verb in WEAK_ACTION_VERBS:
                found_weak[verb] += 1

        score = min(100, len(found_strong) * 15)
        return {"score": score, "strong_verbs_used": dict(found_strong.most_common(10)),
                "weak_verbs_detected": dict(found_weak.most_common(5)),
                "unique_strong_verbs": len(found_strong)}

    # ── Formatting Intelligence ──────────────────────────────────────

    def _analyze_formatting(self, lines: List[str], full_text: str) -> Dict[str, Any]:
        word_count = len(full_text.split())
        if len(lines) > 3:
            avg_line_len = sum(len(l) for l in lines) / len(lines)
        else:
            avg_line_len = 0
        has_sections = bool(re.search(r"(?i)(experience|education|skills|projects|certifications|summary)", full_text))
        findings = []
        if not has_sections:
            findings.append("No standard resume sections detected")
        if avg_line_len > 120:
            findings.append("Lines too long — reduces skimability")
        score = 100 if has_sections else 50
        return {"score": score, "sections_detected": has_sections,
                "avg_line_length": round(avg_line_len, 0), "total_lines": len(lines), "findings": findings}

    # ── Density Analysis ─────────────────────────────────────────────

    def _analyze_density(self, bullets: List[str], words: List[str]) -> Dict[str, Any]:
        word_count = len(words)
        bullet_count = len(bullets)
        density = bullet_count / max(word_count, 1) * 100
        if density < 1.0:
            finding = "Low bullet density: consider converting paragraphs to bullet points"
        elif density > 5.0:
            finding = "High bullet density: may indicate list-heavy format"
        else:
            finding = "Good bullet-to-text ratio"
        return {"score": 80 if 1.0 <= density <= 5.0 else 50,
                "word_count": word_count, "bullet_count": bullet_count,
                "density_pct": round(density, 1), "finding": finding}

    # ── Weak Wording Detection ───────────────────────────────────────

    def _detect_weak_wording(self, text: str) -> Dict[str, Any]:
        found = []
        for phrase in WEAK_PHRASES:
            matches = re.findall(phrase, text, re.IGNORECASE)
            if matches:
                found.append({"phrase": phrase, "count": len(matches)})
        score = max(0, 100 - len(found) * 20)
        return {"score": score, "weak_phrases_detected": found,
                "total_weak_instances": sum(f["count"] for f in found)}

    # ── Achievement Strength ─────────────────────────────────────────

    def _analyze_achievement_strength(self, bullets: List[str]) -> Dict[str, Any]:
        strong, adequate, weak = 0, 0, 0
        for b in bullets:
            has_metric = bool(re.search(r"\b\d+[%kKmM]\b|\b\d+\s*(?:users|customers|requests)", b))
            has_outcome = bool(re.search(r"(?i)(resulting|impact|enabling|achieving|improving|reducing|increasing|saving|generating)", b))
            verb = b.lstrip("-•*· ").split()[0].lower() if b.lstrip("-•*· ").split() else ""
            strong_verb = verb in STRONG_ACTION_VERBS
            if has_metric and strong_verb and has_outcome:
                strong += 1
            elif strong_verb or has_metric:
                adequate += 1
            else:
                weak += 1
        total = max(len(bullets), 1)
        return {"strong": strong, "adequate": adequate, "weak": weak,
                "strong_pct": round(strong / total * 100, 1), "score": round((strong / total) * 100, 1)}

    def _compute_quality_score(self, *analyses: Dict[str, Any]) -> float:
        scores = [a.get("score", 0) for a in analyses if isinstance(a.get("score"), (int, float))]
        return sum(scores) / max(len(scores), 1) if scores else 0.0


_svc: Optional[ResumeAnalysisService] = None
def get_resume_analysis_service() -> ResumeAnalysisService:
    global _svc
    if _svc is None: _svc = ResumeAnalysisService()
    return _svc
def __getattr__(name: str):
    if name == "resume_analysis_service": return get_resume_analysis_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

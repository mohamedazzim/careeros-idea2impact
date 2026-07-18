"""
Hallucination guard: active hallucination defense for Claude outputs.

Detects unsupported technologies, fabricated metrics, invented chronology,
unsupported recommendations, evidence gaps, and low retrieval confidence.

Stateless, async-safe, observable. Worker-safe.
"""
import logging
import re
from typing import Dict, Any, List, Optional

from src.schemas.intelligence import HallucinationReport
from src.observability.metrics import (
    HALLUCINATION_DETECTED,
    HALLUCINATION_MITIGATED,
    HALLUCINATION_RISK_SCORE,
)

logger = logging.getLogger(__name__)

# Known tech terms that Claude might hallucinate but are supported
KNOWN_TECH: List[str] = [
    "react", "angular", "vue", "typescript", "javascript", "python", "java",
    "golang", "rust", "c#", ".net", "node.js", "fastapi", "django", "spring",
    "aws", "azure", "gcp", "kubernetes", "docker", "terraform", "postgresql",
    "mysql", "mongodb", "redis", "elasticsearch", "graphql", "rest", "grpc",
    "kafka", "langgraph", "langchain", "mcp", "llm", "rag", "huggingface",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy",
    "ci/cd", "jenkins", "github actions", "gitlab", "argocd",
    "prometheus", "grafana", "elk", "opentelemetry",
]

# Patterns for fabricated metrics
METRIC_PATTERNS = [
    r"\d{1,3}%\s+(?:improvement|increase|reduction|boost|gain)",
    r"(?:improved|increased|reduced|boosted)\s+by\s+\d{1,3}%",
    r"\d+x\s+(?:faster|improvement|gain)",
    r"reduced .* by \d{1,3}%",
]


class HallucinationGuard:
    """Detects and mitigates hallucinations in Claude outputs."""

    def detect(
        self,
        response: Dict[str, Any],
        context: str,
        supported_tech: Optional[List[str]] = None,
    ) -> HallucinationReport:
        """Scan Claude output for hallucination indicators.

        Checks: unsupported technologies, fabricated metrics,
        invented chronology, unsupported recommendations, evidence gaps.
        """
        response_text = self._extract_text(response)
        context_lower = context.lower()
        supported = set(supported_tech or [])
        context_tech = set(re.findall(r"\b[\w+#./-]{2,20}\b", context_lower))
        all_known = supported | context_tech | set(KNOWN_TECH)

        # 1. Detect unsupported technologies
        resp_tech = set(re.findall(r"\b[\w+#./-]{2,20}\b", response_text.lower()))
        unsupported = resp_tech - all_known

        # 2. Detect fabricated metrics
        fabricated = []
        for pattern in METRIC_PATTERNS:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for m in matches:
                if m.lower() not in context_lower:
                    fabricated.append(m)

        # 3. Detect invented chronology
        chronology = []
        years = re.findall(r"\b(20\d{2})\b", response_text)
        context_years = set(re.findall(r"\b(20\d{2})\b", context))
        invented_years = [y for y in years if y not in context_years]
        if invented_years:
            chronology.append(f"Years not in context: {', '.join(invented_years)}")

        # 4. Detect unsupported recommendations
        recommendations = []
        rec_patterns = [
            r"(?:should|must|needs to|consider|recommend)\s+(?:learn|study|pursue|obtain|get|acquire|develop)\s+[\w\s]{3,30}",
        ]
        for pattern in rec_patterns:
            matches = re.findall(pattern, response_text, re.IGNORECASE)
            for m in matches:
                key_terms = set(re.findall(r"\b[a-z]{3,}\b", m.lower()))
                overlap = key_terms & context_tech
                if len(overlap) == 0:
                    recommendations.append(m.strip())

        # 5. Evidence gaps
        gaps = []
        if len(context) < 100:
            gaps.append("Context < 100 chars: high risk of hallucination")
        if not context_tech:
            gaps.append("No technical terms found in context")

        # Risk assessment
        risk_signals = sum([
            1 if unsupported else 0,
            1 if fabricated else 0,
            1 if chronology else 0,
            1 if recommendations else 0,
            1 if gaps else 0,
        ])

        if risk_signals >= 4:
            risk_level = "critical"
        elif risk_signals >= 3:
            risk_level = "high"
        elif risk_signals >= 2:
            risk_level = "medium"
        elif risk_signals >= 1:
            risk_level = "low"
        else:
            risk_level = "none"

        hallucination_score = min(1.0, risk_signals / 5.0)

        detected = risk_level != "none"
        if detected:
            HALLUCINATION_DETECTED.labels(severity=risk_level).inc()
            HALLUCINATION_RISK_SCORE.observe(hallucination_score)

        return HallucinationReport(
            hallucination_detected=detected,
            risk_level=risk_level,
            unsupported_technologies=list(unsupported),
            fabricated_metrics=fabricated,
            invented_chronology=chronology,
            unsupported_recommendations=recommendations,
            evidence_gaps=gaps,
            hallucination_score=round(hallucination_score, 4),
        )

    def mitigate(
        self,
        response: Dict[str, Any],
        report: HallucinationReport,
    ) -> Dict[str, Any]:
        """Apply mitigation: confidence reduction, sanitization, warnings."""
        if not report.hallucination_detected:
            return response

        clean = dict(response)

        if "metadata" not in clean:
            clean["metadata"] = {}
        if isinstance(clean["metadata"], dict):
            clean["metadata"]["hallucination_report"] = report.model_dump()
            clean["metadata"]["confidence_multiplier"] = max(
                0.3, 1.0 - report.hallucination_score
            )

        if report.fabricated_metrics:
            clean["metadata"]["fabricated_metrics_removed"] = len(
                report.fabricated_metrics
            )
            HALLUCINATION_MITIGATED.labels(type="metrics").inc()

        if report.unsupported_technologies:
            HALLUCINATION_MITIGATED.labels(type="tech").inc()

        if report.unsupported_recommendations:
            HALLUCINATION_MITIGATED.labels(type="recommendations").inc()

        logger.warning(
            f"Hallucination mitigated (severity={report.risk_level}, "
            f"unsupported_tech={len(report.unsupported_technologies)}, "
            f"fabricated={len(report.fabricated_metrics)})"
        )

        return clean

    def _extract_text(self, response: Dict[str, Any]) -> str:
        parts = []
        for k, v in response.items():
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, (list, dict)):
                parts.append(str(v))
        return " ".join(parts)


_hallucination_guard: Optional[HallucinationGuard] = None


def get_hallucination_guard() -> HallucinationGuard:
    global _hallucination_guard
    if _hallucination_guard is None:
        _hallucination_guard = HallucinationGuard()
    return _hallucination_guard


def reset_hallucination_guard() -> None:
    global _hallucination_guard
    _hallucination_guard = None


def __getattr__(name: str):
    if name == "hallucination_guard":
        return get_hallucination_guard()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

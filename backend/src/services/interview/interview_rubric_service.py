"""
Interview rubric service — structured evaluation rubrics for all interview types.

Each rubric dimension is scored 0-100 with evidence citations required.
Rubrics drive consistent, explainable, goverance-compliant evaluation.

Phase 4D: Explainable interview evaluation.
"""
import logging
from typing import Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RubricDimension:
    name: str
    description: str
    weight: float = 1.0
    evidence_required: bool = True
    score_range: tuple = (0, 100)


class InterviewRubricService:
    def get_technical_rubric(self) -> List[RubricDimension]:
        return [
            RubricDimension("technical_depth", "Depth of technical knowledge demonstrated", 1.5),
            RubricDimension("problem_solving", "Systematic approach to problem decomposition", 1.5),
            RubricDimension("architecture_reasoning", "Ability to reason about system architecture", 1.2),
            RubricDimension("tradeoff_awareness", "Understanding of engineering tradeoffs", 1.0),
            RubricDimension("production_realism", "Real-world deployment and operational awareness", 1.2),
            RubricDimension("communication_clarity", "Clarity and precision of technical communication", 1.0),
        ]

    def get_coding_rubric(self) -> List[RubricDimension]:
        return [
            RubricDimension("algorithmic_thinking", "Algorithm design and complexity analysis", 1.5),
            RubricDimension("code_quality", "Code structure, readability, and patterns", 1.3),
            RubricDimension("edge_case_handling", "Identification and handling of edge cases", 1.2),
            RubricDimension("testing_approach", "Test strategy and validation reasoning", 1.0),
            RubricDimension("optimization_reasoning", "Performance optimization analysis", 1.2),
            RubricDimension("language_proficiency", "Depth in chosen language/framework", 1.0),
        ]

    def get_system_design_rubric(self) -> List[RubricDimension]:
        return [
            RubricDimension("scalability_reasoning", "Horizontal/vertical scaling analysis", 1.5),
            RubricDimension("architecture_decomposition", "Service decomposition and boundary definition", 1.5),
            RubricDimension("fault_tolerance", "Failure mode analysis and resilience design", 1.3),
            RubricDimension("observability_reasoning", "Monitoring, logging, tracing design", 1.0),
            RubricDimension("async_orchestration", "Event-driven and async workflow design", 1.2),
            RubricDimension("governance_reasoning", "Security, compliance, cost optimization", 1.0),
            RubricDimension("deployment_reasoning", "CI/CD, infrastructure, rollout strategy", 1.0),
            RubricDimension("tradeoff_reasoning", "Explicit tradeoff analysis and justification", 1.2),
        ]

    def get_ai_engineering_rubric(self) -> List[RubricDimension]:
        return [
            RubricDimension("rag_understanding", "Retrieval-augmented generation comprehension", 1.5),
            RubricDimension("vector_db_reasoning", "Vector database and embedding understanding", 1.3),
            RubricDimension("orchestration_reasoning", "AI pipeline and agent orchestration", 1.5),
            RubricDimension("governance_understanding", "AI safety, hallucination mitigation, evaluation", 1.3),
            RubricDimension("mcp_understanding", "Model context protocol and tool integration", 1.0),
            RubricDimension("langgraph_understanding", "LangGraph and stateful AI workflows", 1.2),
            RubricDimension("inference_optimization", "Model serving and inference optimization", 1.2),
            RubricDimension("production_ai", "Production AI deployment and monitoring", 1.3),
        ]

    def get_behavioral_rubric(self) -> List[RubricDimension]:
        return [
            RubricDimension("leadership_signals", "Evidence of leadership and initiative", 1.3),
            RubricDimension("conflict_resolution", "Conflict handling and resolution approach", 1.2),
            RubricDimension("collaboration_patterns", "Cross-functional collaboration evidence", 1.0),
            RubricDimension("growth_mindset", "Learning agility and adaptation signals", 1.2),
            RubricDimension("impact_communication", "Ability to articulate impact and outcomes", 1.3),
            RubricDimension("stakeholder_management", "Managing up and across organizations", 1.0),
            RubricDimension("failure_response", "Response to setbacks and failure patterns", 1.2),
        ]

    def score_dimension(
        self, dimension: RubricDimension, evaluation: Dict[str, Any]
    ) -> Dict[str, Any]:
        raw = evaluation.get(dimension.name, 50)
        citations = evaluation.get("citations", [])
        dim_citations = [c for c in citations if c.get("dimension") == dimension.name]

        return {
            "dimension": dimension.name,
            "score": min(100, max(0, raw)),
            "weight": dimension.weight,
            "evidence_quality": min(1.0, len(dim_citations) / 2.0),
            "citations": dim_citations,
            "evidence_sufficient": len(dim_citations) >= 1,
        }

    def compute_weighted_score(
        self, rubrics: List[RubricDimension], scores: Dict[str, float]
    ) -> Dict[str, Any]:
        total_weight = sum(d.weight for d in rubrics)
        weighted_sum = sum(scores.get(d.name, 0) * d.weight for d in rubrics)
        overall = round(weighted_sum / max(total_weight, 1), 1)

        return {
            "overall_score": overall,
            "dimension_count": len(rubrics),
            "per_dimension": {
                d.name: {
                    "score": scores.get(d.name, 0),
                    "weight": d.weight,
                    "contribution": round(scores.get(d.name, 0) * d.weight / max(total_weight, 1), 1),
                }
                for d in rubrics
            },
        }


_svc: InterviewRubricService | None = None


def get_interview_rubric_service() -> InterviewRubricService:
    global _svc
    if _svc is None:
        _svc = InterviewRubricService()
    return _svc


def __getattr__(name: str):
    if name == "interview_rubric_service":
        return get_interview_rubric_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

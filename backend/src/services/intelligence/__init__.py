"""
Claude Intelligence Orchestration Layer — Phases 4A + 4B.

Production Claude Sonnet 4.6 integration with:
- Retrieval-grounded reasoning
- ATS scoring (14 categories)
- Semantic job-fit analysis
- Skill-gap intelligence
- Recruiter-grade evaluation
- Achievement impact analysis
- Evidence-grounded recommendations
- Prompt governance with versioning
- Hallucination defense
- Multi-factor confidence scoring
- Structured output validation
- Citation alignment
- Full observability

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
from .claude_service import ClaudeService
from .prompt_builder import PromptBuilder
from .reasoning_pipeline import ReasoningPipeline
from .grounding_guard import GroundingGuard
from .output_validator import OutputValidator
from .confidence_engine import ConfidenceEngine
from .citation_alignment import CitationAlignment
from .hallucination_guard import HallucinationGuard
from .structured_response_builder import StructuredResponseBuilder
from .prompt_versioning import get_active, list_all as list_prompts
from .response_schema_registry import get_schema, register_schema
from .intelligence_observability import IntelligenceObservability
# Phase 4B
from .ats_scoring_service import ATSScoringService
from .skill_gap_service import SkillGapService
from .semantic_fit_service import SemanticFitService
from .recruiter_evaluation_service import RecruiterEvaluationService
from .achievement_analysis_service import AchievementAnalysisService
from .recommendation_engine import RecommendationEngine
from .evidence_scorer import EvidenceScorer
from .score_calibration import ScoreCalibration
from .reasoning_trace_builder import ReasoningTraceBuilder
from .intelligence_schema_registry import list_all as list_intelligence_schemas
from .intelligence_metrics import IntelligenceMetrics
# Phase 4B Hardening
from .resume_analysis_service import ResumeAnalysisService
from .contradiction_analysis_service import ContradictionAnalyzer
from .hardened_recommendation_engine import HardenedRecommendationEngine

__all__ = [
    # Phase 4A
    "ClaudeService",
    "PromptBuilder",
    "ReasoningPipeline",
    "GroundingGuard",
    "OutputValidator",
    "ConfidenceEngine",
    "CitationAlignment",
    "HallucinationGuard",
    "StructuredResponseBuilder",
    "IntelligenceObservability",
    "get_active",
    "list_prompts",
    "get_schema",
    "register_schema",
    # Phase 4B
    "ATSScoringService",
    "SkillGapService",
    "SemanticFitService",
    "RecruiterEvaluationService",
    "AchievementAnalysisService",
    "RecommendationEngine",
    "EvidenceScorer",
    "ScoreCalibration",
    "ReasoningTraceBuilder",
    "list_intelligence_schemas",
    "IntelligenceMetrics",
    # Phase 4B Hardening
    "ResumeAnalysisService",
    "ContradictionAnalyzer",
    "HardenedRecommendationEngine",
    # Singletons
    "claude_service", "prompt_builder", "reasoning_pipeline",
    "grounding_guard", "output_validator", "confidence_engine",
    "citation_alignment", "hallucination_guard",
    "structured_response_builder", "intelligence_observability",
    "ats_scoring_service", "skill_gap_service", "semantic_fit_service",
    "recruiter_evaluation_service", "achievement_analysis_service",
    "recommendation_engine", "evidence_scorer", "score_calibration",
    "reasoning_trace_builder", "intelligence_metrics",
    "resume_analysis_service", "contradiction_analyzer",
    "hardened_recommendation_engine",
]


def __getattr__(name: str):
    if name == "claude_service":
        from .claude_service import get_claude_service; return get_claude_service()
    if name == "prompt_builder":
        from .prompt_builder import get_prompt_builder; return get_prompt_builder()
    if name == "reasoning_pipeline":
        from .reasoning_pipeline import get_reasoning_pipeline; return get_reasoning_pipeline()
    if name == "grounding_guard":
        from .grounding_guard import get_grounding_guard; return get_grounding_guard()
    if name == "output_validator":
        from .output_validator import get_output_validator; return get_output_validator()
    if name == "confidence_engine":
        from .confidence_engine import get_confidence_engine; return get_confidence_engine()
    if name == "citation_alignment":
        from .citation_alignment import get_citation_alignment; return get_citation_alignment()
    if name == "hallucination_guard":
        from .hallucination_guard import get_hallucination_guard; return get_hallucination_guard()
    if name == "structured_response_builder":
        from .structured_response_builder import get_structured_response_builder; return get_structured_response_builder()
    if name == "intelligence_observability":
        from .intelligence_observability import get_intelligence_observability; return get_intelligence_observability()
    if name == "ats_scoring_service":
        from .ats_scoring_service import get_ats_scoring_service; return get_ats_scoring_service()
    if name == "skill_gap_service":
        from .skill_gap_service import get_skill_gap_service; return get_skill_gap_service()
    if name == "semantic_fit_service":
        from .semantic_fit_service import get_semantic_fit_service; return get_semantic_fit_service()
    if name == "recruiter_evaluation_service":
        from .recruiter_evaluation_service import get_recruiter_evaluation_service; return get_recruiter_evaluation_service()
    if name == "achievement_analysis_service":
        from .achievement_analysis_service import get_achievement_analysis_service; return get_achievement_analysis_service()
    if name == "recommendation_engine":
        from .recommendation_engine import get_recommendation_engine; return get_recommendation_engine()
    if name == "evidence_scorer":
        from .evidence_scorer import get_evidence_scorer; return get_evidence_scorer()
    if name == "score_calibration":
        from .score_calibration import get_score_calibration; return get_score_calibration()
    if name == "reasoning_trace_builder":
        from .reasoning_trace_builder import get_reasoning_trace_builder; return get_reasoning_trace_builder()
    if name == "intelligence_metrics":
        from .intelligence_metrics import get_intelligence_metrics; return get_intelligence_metrics()
    if name == "resume_analysis_service":
        from .resume_analysis_service import get_resume_analysis_service; return get_resume_analysis_service()
    if name == "contradiction_analyzer":
        from .contradiction_analysis_service import get_contradiction_analyzer; return get_contradiction_analyzer()
    if name == "hardened_recommendation_engine":
        from .hardened_recommendation_engine import get_hardened_recommendation_engine; return get_hardened_recommendation_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

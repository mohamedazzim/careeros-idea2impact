"""
Interview intelligence services — adaptive AI interview platform.

Phase 4D: Full interview intelligence stack with adaptive questioning,
evidence-grounded evaluation, real-time critique, weakness pattern detection,
and full explainability traces.

Services:
- interview_orchestrator.py: State-aware session engine
- adaptive_difficulty_service.py: Real-time difficulty adaptation
- technical_interview_service.py: Technical question generation + evaluation
- coding_interview_service.py: Coding interview intelligence
- system_design_service.py: System design scenario evaluation
- behavioral_interview_service.py: STAR-method behavioral interviewing
- ai_engineering_interview_service.py: AI/ML engineering evaluation
- realtime_feedback_service.py: Live critique with evidence citations
- weakness_pattern_service.py: Longitudinal pattern detection
- interview_memory_service.py: Session state and history
- interview_confidence_engine.py: Per-question/session confidence calibration
- interview_evaluation_service.py: Weighted multi-rubric scoring
- interview_rubric_service.py: Structured evaluation rubrics
- interview_trace_builder.py: Full explainability chain
- interview_governance.py: Hallucination and critique validation
- interview_observability.py: Domain-specific metrics
"""

__all__ = [
    "InterviewOrchestrator", "get_interview_orchestrator",
    "AdaptiveDifficultyService", "get_adaptive_difficulty_service",
    "InterviewMemoryService", "get_interview_memory_service",
    "InterviewEvaluationService", "get_interview_evaluation_service",
    "InterviewConfidenceEngine", "get_interview_confidence_engine",
    "InterviewRubricService", "get_interview_rubric_service",
    "InterviewGovernance", "get_interview_governance",
    "InterviewObservability", "get_interview_observability",
    "InterviewTraceBuilder", "get_interview_trace_builder",
    "RealtimeFeedbackService", "get_realtime_feedback_service",
    "WeaknessPatternService", "get_weakness_pattern_service",
    "TechnicalInterviewService", "get_technical_interview_service",
    "CodingInterviewService", "get_coding_interview_service",
    "SystemDesignService", "get_system_design_service",
    "BehavioralInterviewService", "get_behavioral_interview_service",
    "AIEngineeringInterviewService", "get_ai_engineering_interview_service",
]


def __getattr__(name: str):
    if name == "interview_orchestrator":
        from src.services.interview.interview_orchestrator import get_interview_orchestrator
        return get_interview_orchestrator()
    if name == "adaptive_difficulty_service":
        from src.services.interview.adaptive_difficulty_service import get_adaptive_difficulty_service
        return get_adaptive_difficulty_service()
    if name == "interview_memory_service":
        from src.services.interview.interview_memory_service import get_interview_memory_service
        return get_interview_memory_service()
    if name == "interview_evaluation_service":
        from src.services.interview.interview_evaluation_service import get_interview_evaluation_service
        return get_interview_evaluation_service()
    if name == "interview_confidence_engine":
        from src.services.interview.interview_confidence_engine import get_interview_confidence_engine
        return get_interview_confidence_engine()
    if name == "interview_rubric_service":
        from src.services.interview.interview_rubric_service import get_interview_rubric_service
        return get_interview_rubric_service()
    if name == "interview_governance":
        from src.services.interview.interview_governance import get_interview_governance
        return get_interview_governance()
    if name == "interview_observability":
        from src.services.interview.interview_observability import get_interview_observability
        return get_interview_observability()
    if name == "interview_trace_builder":
        from src.services.interview.interview_trace_builder import get_interview_trace_builder
        return get_interview_trace_builder()
    if name == "realtime_feedback_service":
        from src.services.interview.realtime_feedback_service import get_realtime_feedback_service
        return get_realtime_feedback_service()
    if name == "weakness_pattern_service":
        from src.services.interview.weakness_pattern_service import get_weakness_pattern_service
        return get_weakness_pattern_service()
    if name == "technical_interview_service":
        from src.services.interview.technical_interview_service import get_technical_interview_service
        return get_technical_interview_service()
    if name == "coding_interview_service":
        from src.services.interview.coding_interview_service import get_coding_interview_service
        return get_coding_interview_service()
    if name == "system_design_service":
        from src.services.interview.system_design_service import get_system_design_service
        return get_system_design_service()
    if name == "behavioral_interview_service":
        from src.services.interview.behavioral_interview_service import get_behavioral_interview_service
        return get_behavioral_interview_service()
    if name == "ai_engineering_interview_service":
        from src.services.interview.ai_engineering_interview_service import get_ai_engineering_interview_service
        return get_ai_engineering_interview_service()
    if name == "interview_persistence_service":
        from src.services.interview.interview_persistence_service import get_interview_persistence_service
        return get_interview_persistence_service()
    if name == "interview_concurrency_service":
        from src.services.interview.interview_concurrency_service import get_interview_concurrency_service
        return get_interview_concurrency_service()
    if name == "interview_state_validator":
        from src.services.interview.interview_state_validator import get_interview_state_validator
        return get_interview_state_validator()
    if name == "interview_safety_service":
        from src.services.interview.interview_safety_service import get_interview_safety_service
        return get_interview_safety_service()
    if name == "streaming_orchestrator":
        from src.services.interview.streaming_readiness import get_streaming_orchestrator
        return get_streaming_orchestrator()
    if name == "coding_governance":
        from src.services.interview.coding_interview_governance import get_coding_governance
        return get_coding_governance()
    if name == "persistence_service":
        from src.services.interview.interview_persistence_service import get_interview_persistence_service
        return get_interview_persistence_service()
    if name == "evaluation_service":
        from src.services.interview.interview_evaluation_service import get_interview_evaluation_service
        return get_interview_evaluation_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

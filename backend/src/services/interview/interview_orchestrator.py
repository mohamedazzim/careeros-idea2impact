"""
Interview orchestrator — state-aware multi-type interview session engine.

Orchestrates full interview lifecycle:
- Session initialization with difficulty calibration
- Question generation (technical, coding, system_design, behavioral, ai_engineering)
- Answer evaluation with rubric scoring
- Real-time feedback generation
- Adaptive difficulty progression
- Session closure with weakness pattern detection
- Full explainability traces

Phase 4D: Adaptive interview intelligence orchestrator.

LangGraph-compatible, stateless, async-safe, governance-ready.
"""
import time
import json
import logging
import uuid
from typing import Dict, Any, Optional

from src.services.interview.interview_memory_service import get_interview_memory_service
from src.services.interview.adaptive_difficulty_service import get_adaptive_difficulty_service
from src.services.interview.interview_evaluation_service import get_interview_evaluation_service
from src.services.interview.interview_trace_builder import get_interview_trace_builder
from src.services.interview.interview_governance import get_interview_governance
from src.services.interview.interview_observability import get_interview_observability
from src.services.interview.interview_rubric_service import get_interview_rubric_service
from src.services.interview.realtime_feedback_service import get_realtime_feedback_service
from src.services.interview.system_design_service import get_system_design_service
from src.services.interview.weakness_pattern_service import get_weakness_pattern_service

logger = logging.getLogger(__name__)

INTERVIEW_TYPES = ["technical", "coding", "system_design", "behavioral", "ai_engineering"]


class InterviewOrchestrator:
    """State-aware adaptive interview orchestrator.

    Manages complete interview sessions: initialization → question loop →
    evaluation → feedback → adaptation → close → patterns.
    """

    async def initialize_session(
        self,
        interview_type: str,
        resume_text: str = "",
        ats_data: Optional[Dict[str, Any]] = None,
        ai_readiness: Optional[Dict[str, Any]] = None,
        architecture_maturity: Optional[Dict[str, Any]] = None,
        strategy_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if interview_type not in INTERVIEW_TYPES:
            return {"error": f"Unknown interview_type '{interview_type}'", "valid_types": INTERVIEW_TYPES}

        obs = get_interview_observability()
        memory = get_interview_memory_service()
        difficulty_svc = get_adaptive_difficulty_service()

        session_id = str(uuid.uuid4())[:12]
        initial_level = difficulty_svc.compute_initial_level(
            ats_data=ats_data,
            ai_readiness=ai_readiness,
            architecture_maturity=architecture_maturity,
            strategy_data=strategy_data,
        )

        session = memory.create_session(
            session_id=session_id,
            interview_type=interview_type,
            difficulty_level=initial_level,
            metadata={
                **(metadata or {}),
                "has_ats": ats_data is not None,
                "has_ai_readiness": ai_readiness is not None,
                "has_architecture": architecture_maturity is not None,
            },
        )

        past = memory.get_past_sessions(interview_type=interview_type, limit=5)
        obs.record_concurrency_pressure(len(memory.sessions))

        return {
            "session_id": session_id,
            "interview_type": interview_type,
            "difficulty_level": initial_level,
            "past_interviews": past,
            "question_count": 0,
            "session_metadata": session.metadata,
        }

    async def generate_next_question(
        self,
        session_id: str,
        resume_text: str = "",
        ats_data: Optional[Dict[str, Any]] = None,
        ai_readiness: Optional[Dict[str, Any]] = None,
        strategy_data: Optional[Dict[str, Any]] = None,
        context: str = "",
    ) -> Dict[str, Any]:
        mem = get_interview_memory_service()
        session = mem.get_session(session_id)
        if not session:
            return {"error": "session_not_found", "session_id": session_id}

        difficulty_svc = get_adaptive_difficulty_service()
        difficulty_decision = difficulty_svc.adapt(
            session.difficulty_level,
            session.questions,
            ats_data=ats_data,
            ai_readiness=ai_readiness,
        )
        level = difficulty_decision["level"]

        interview_type = session.interview_type
        question_data = None

        if interview_type == "technical":
            from src.services.interview.technical_interview_service import get_technical_interview_service
            svc = get_technical_interview_service()
            response = await svc.generate_question(
                resume_text=resume_text,
                difficulty=level,
                domain="backend_engineering",
                question_history=session.questions,
                context=context,
            )
            question_data = self._extract_question(response)

        elif interview_type == "coding":
            from src.services.interview.coding_interview_service import get_coding_interview_service
            svc = get_coding_interview_service()
            response = await svc.generate_question(
                resume_text=resume_text,
                difficulty=level,
                domain="algorithms",
                question_history=session.questions,
                context=context,
            )
            question_data = self._extract_question(response)

        elif interview_type == "system_design":
            svc = get_system_design_service()
            arch_mat = json.dumps(ats_data or {}, default=str)
            response = await svc.generate_scenario(
                resume_text=resume_text,
                difficulty=level,
                architecture_maturity=arch_mat,
                context=context,
            )
            question_data = self._extract_question(response)

        elif interview_type == "behavioral":
            from src.services.interview.behavioral_interview_service import get_behavioral_interview_service
            svc = get_behavioral_interview_service()
            response = await svc.generate_question(
                resume_text=resume_text,
                difficulty=level,
                category="leadership",
                recruiter_signals=json.dumps(ats_data or {}, default=str),
                context=context,
            )
            question_data = self._extract_question(response)

        elif interview_type == "ai_engineering":
            from src.services.interview.ai_engineering_interview_service import get_ai_engineering_interview_service
            svc = get_ai_engineering_interview_service()
            response = await svc.generate_question(
                resume_text=resume_text,
                difficulty=level,
                domain="rag_systems",
                ai_readiness_signals=json.dumps(ai_readiness or {}, default=str),
                context=context,
            )
            question_data = self._extract_question(response)

        if not question_data:
            return {"error": "question_generation_failed"}

        question_data["difficulty_level"] = level
        question_data["difficulty_decision"] = difficulty_decision
        mem.add_question(session_id, question_data)

        return {
            "session_id": session_id,
            "question": question_data.get("question", ""),
            "question_id": question_data.get("question_id", str(len(session.questions))),
            "question_index": session.current_question_index,
            "difficulty": level,
            "difficulty_decision": difficulty_decision,
            "interview_type": interview_type,
        }

    async def evaluate_answer(
        self,
        session_id: str,
        question: str,
        answer: str,
        resume_text: str = "",
        context: str = "",
    ) -> Dict[str, Any]:
        mem = get_interview_memory_service()
        session = mem.get_session(session_id)
        if not session:
            return {"error": "session_not_found"}

        obs = get_interview_observability()
        start = time.monotonic()
        interview_type = session.interview_type
        difficulty = session.difficulty_level

        # Run type-specific evaluation via reasoning pipeline
        eval_svc = get_interview_evaluation_service()
        rubric_svc = get_interview_rubric_service()

        rubric_map = {
            "technical": rubric_svc.get_technical_rubric,
            "coding": rubric_svc.get_coding_rubric,
            "system_design": rubric_svc.get_system_design_rubric,
            "ai_engineering": rubric_svc.get_ai_engineering_rubric,
            "behavioral": rubric_svc.get_behavioral_rubric,
        }
        rubric = (rubric_map.get(interview_type, rubric_svc.get_technical_rubric))()

        claude_eval = await self._run_claude_evaluation(
            interview_type=interview_type,
            question=question,
            answer=answer,
            difficulty=difficulty,
            candidate_context=resume_text,
            context=context,
        )

        evaluation = await eval_svc.evaluate(
            interview_type=interview_type,
            question=question,
            answer=answer,
            difficulty=difficulty,
            claude_evaluation=claude_eval,
            answer_history=session.questions,
        )

        # Governance validation
        governance = get_interview_governance()
        governance_result = governance.validate_evaluation(
            evaluation=evaluation,
            rubric=rubric,
            evidence_context=resume_text,
        )

        # Feedback
        feedback_svc = get_realtime_feedback_service()
        feedback = await feedback_svc.critique(
            question=question,
            answer=answer,
            interview_type=interview_type,
            difficulty=difficulty,
            candidate_context=resume_text,
        )

        # Update session
        evaluation["contradiction_detected"] = False
        mem.add_question(session_id, evaluation)

        # Difficulty adaptation
        diff_svc = get_adaptive_difficulty_service()
        difficulty_decision = diff_svc.adapt(
            session.difficulty_level,
            session.questions,
        )

        elapsed = (time.monotonic() - start) * 1000
        obs.record_interview_call(interview_type, "success", elapsed)

        # Trace
        trace = get_interview_trace_builder().build_trace(
            session_id=session_id,
            question_index=session.current_question_index,
            evaluation=evaluation,
            difficulty_decision=difficulty_decision,
            claude_raw=claude_eval,
        )

        return {
            "session_id": session_id,
            "evaluation": evaluation,
            "governance": governance_result,
            "feedback": self._extract_data(feedback),
            "difficulty_decision": difficulty_decision,
            "trace": trace,
        }

    async def close_session(
        self,
        session_id: str,
        resume_text: str = "",
        strategy_data: str = "",
        learning_path: str = "",
        context: str = "",
    ) -> Dict[str, Any]:
        mem = get_interview_memory_service()
        session = mem.get_session(session_id)
        if not session:
            return {"error": "session_not_found"}

        session_summary = mem.close_session(session_id)
        past_sessions = mem.get_past_sessions(limit=10)

        pattern_svc = get_weakness_pattern_service()
        patterns = pattern_svc.detect_patterns(
            session_history=past_sessions,
            question_history=session.questions,
        )

        growth_plan = None
        if patterns.get("total_patterns_detected", 0) > 0:
            growth = await pattern_svc.generate_growth_plan(
                patterns=patterns,
                strategy_data=strategy_data,
                learning_path=learning_path,
                context=context,
            )
            growth_plan = self._extract_data(growth)

        from src.services.interview.realtime_feedback_service import get_realtime_feedback_service
        feedback_svc = get_realtime_feedback_service()
        summary_feedback = await feedback_svc.generate_feedback_summary(
            session_questions=session.questions,
            interview_type=session.interview_type,
            context=context,
        )

        traces = []
        for q in session.questions:
            if isinstance(q, dict) and "trace" not in q and q.get("question"):
                traces.append({
                    "question": q.get("question", "")[:100],
                    "score": q.get("score", 0),
                    "difficulty": q.get("difficulty", session.difficulty_level),
                })

        trace_builder = get_interview_trace_builder()
        session_trace = trace_builder.build_session_trace(
            session_id=session_id,
            question_traces=traces,
            session_summary=session_summary,
            weakness_patterns=patterns,
        )

        return {
            "session_summary": session_summary,
            "weakness_patterns": patterns,
            "growth_plan": growth_plan,
            "feedback_summary": self._extract_data(summary_feedback),
            "session_trace": session_trace,
        }

    async def _run_claude_evaluation(
        self,
        interview_type: str,
        question: str,
        answer: str,
        difficulty: str,
        candidate_context: str = "",
        context: str = "",
    ) -> Dict[str, Any]:
        from src.services.intelligence.reasoning_pipeline import get_reasoning_pipeline

        prompt_id_map = {
            "technical": "technical_evaluation",
            "coding": "coding_evaluation",
            "system_design": "system_design_evaluation",
            "ai_engineering": "ai_engineering_evaluation",
            "behavioral": "behavioral_evaluation",
        }
        prompt_id = prompt_id_map.get(interview_type, "technical_evaluation")

        pipeline = get_reasoning_pipeline()
        result = await pipeline.reason(
            query=f"evaluate {interview_type} answer {difficulty}",
            category="interview",
            prompt_id=prompt_id,
            template_vars={
                "question": question,
                "answer": answer,
                "difficulty": difficulty,
                "interview_type": interview_type,
                "candidate_context": candidate_context,
                "context": context,
            },
        )
        if hasattr(result, "data"):
            return result.data if isinstance(result.data, dict) else {}
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return result if isinstance(result, dict) else {}

    def _extract_question(self, response: Any) -> Dict[str, Any]:
        if hasattr(response, "data"):
            d = response.data
            return d if isinstance(d, dict) else {"question": str(d)}
        if hasattr(response, "model_dump"):
            return response.model_dump()
        return response if isinstance(response, dict) else {"question": str(response)}

    def _extract_data(self, response: Any) -> Any:
        if hasattr(response, "data"):
            return response.data
        if hasattr(response, "model_dump"):
            return response.model_dump()
        return response


_svc: InterviewOrchestrator | None = None
def get_interview_orchestrator() -> InterviewOrchestrator:
    global _svc
    if _svc is None: _svc = InterviewOrchestrator()
    return _svc
def __getattr__(n):
    if n == "interview_orchestrator": return get_interview_orchestrator()
    raise AttributeError(f"module {__name__!r} has no attribute {n!r}")

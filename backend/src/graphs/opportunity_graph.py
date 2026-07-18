"""Phase 5 — Opportunity Orchestration Graph.

LangGraph execution graph with conditional routing, checkpoint persistence,
and retry-safe execution.

Flow:
  START → candidate_context → resume_context → market_context → deadline_context
  → evaluate_fit → evaluate_urgency → generate_priority → governance_validation
  → notification_decision ─┬→ should_notify=True → voice_synthesis → twilio_call
                           └→ should_notify=False →────→ trace_compilation
  → END

All langgraph imports are lazy — graph compiles only when invoked.
"""

import logging
import asyncio

from src.observability.tracing import trace_async

logger = logging.getLogger(__name__)


async def _persist_opportunity_scores(user_id: str, session_uid: str, scored_opportunities: list) -> None:
    """Persist scored opportunities to the opportunity_scores table."""
    if not scored_opportunities:
        return
    import json as _json
    from src.db.session import async_session
    from sqlalchemy import text
    async with async_session() as db:
        for opp in scored_opportunities[:20]:  # top 20
            dim_scores = opp.get("dimension_scores", {})
            weights = {k: v.get("weight", 0.05) for k, v in dim_scores.items() if isinstance(v, dict)}
            await db.execute(text(
                "INSERT INTO opportunity_scores "
                "(opportunity_id, user_id, session_id, overall_score, confidence, "
                "dimension_scores, dimension_weights, evidence_citations, "
                "urgency_score, generated_by, trace_id) "
                "SELECT :oid, :uid, os.id, :score, :conf, CAST(:dims AS jsonb), "
                "CAST(:weights AS jsonb), CAST(:cites AS jsonb), "
                ":urg, :gen, :trace "
                "FROM orchestration_sessions os WHERE os.session_uid = :suid "
                "ON CONFLICT (opportunity_id, user_id, session_id) DO UPDATE SET "
                "overall_score=EXCLUDED.overall_score, confidence=EXCLUDED.confidence, "
                "dimension_scores=EXCLUDED.dimension_scores, urgency_score=EXCLUDED.urgency_score"
            ), {
                "oid": opp.get("opportunity_id", ""),
                "uid": user_id,
                "suid": session_uid,
                "score": opp.get("overall_score", 0),
                "conf": opp.get("confidence", 0.5),
                "dims": _json.dumps(dim_scores),
                "weights": _json.dumps(weights),
                "cites": "[]",
                "urg": opp.get("urgency_score", 0),
                "gen": "opportunity_graph",
                "trace": session_uid,
            })
        await db.commit()
        logger.info(f"Persisted {min(len(scored_opportunities), 20)} scores for session {session_uid}")

_opportunity_graph = None


def build_opportunity_graph():
    """Build and compile the LangGraph opportunity orchestration graph."""
    from langgraph.graph import StateGraph, START, END
    from src.services.checkpoint import get_checkpoint_saver

    memory = get_checkpoint_saver()
    workflow = StateGraph(dict)

    try:
        from langgraph.pregel import RetryPolicy
        retry_policy = RetryPolicy(initial_interval=1, backoff_factor=2, max_attempts=3)
    except ImportError:
        retry_policy = None

    add_kwargs = {}
    if retry_policy:
        try:
            class _TestWorkflow(StateGraph):
                pass
            _test = _TestWorkflow(dict)
            _test.add_node("_test_probe", lambda s: s, retry=retry_policy)
            add_kwargs["retry"] = retry_policy
        except TypeError:
            pass

    nodes = [
        ("retrieve_candidate_context", _retrieve_candidate_context),
        ("retrieve_market_context", _retrieve_market_context),
        # ("retrieve_deadline_context", _retrieve_deadline_context),  # REMOVED: deadline logic removed per new business rules
        ("evaluate_opportunity_fit", _evaluate_opportunity_fit),
        ("evaluate_urgency", _evaluate_urgency),
        ("generate_priority_score", _generate_priority_score),
        ("governance_validation", _governance_validation),
        ("notification_decision", _notification_decision),
        ("voice_synthesis", _voice_synthesis),
        ("twilio_call_execution", _twilio_call_execution),
        ("trace_compilation", _trace_compilation),
    ]
    for name, func in nodes:
        non_retry = {"trace_compilation"}
        kwargs = {} if name in non_retry else add_kwargs
        workflow.add_node(name, func, **kwargs)

    # Linear pipeline: START → ... → notification_decision
    workflow.add_edge(START, "retrieve_candidate_context")
    workflow.add_edge("retrieve_candidate_context", "retrieve_market_context")
    workflow.add_edge("retrieve_market_context", "evaluate_opportunity_fit")
    workflow.add_edge("evaluate_opportunity_fit", "evaluate_urgency")
    workflow.add_edge("evaluate_urgency", "generate_priority_score")
    workflow.add_edge("generate_priority_score", "governance_validation")
    workflow.add_edge("governance_validation", "notification_decision")

    # Conditional routing: notification_decision → voice_synthesis OR trace_compilation
    workflow.add_conditional_edges(
        "notification_decision",
        _route_after_notification,
        {
            "voice_synthesis": "voice_synthesis",
            "trace_compilation": "trace_compilation",
        },
    )

    # Voice pipeline → twilio → trace
    workflow.add_edge("voice_synthesis", "twilio_call_execution")
    workflow.add_edge("twilio_call_execution", "trace_compilation")
    workflow.add_edge("trace_compilation", END)

    return workflow.compile(checkpointer=memory)


def _route_after_notification(state: dict) -> str:
    should_notify = state.get("should_notify", False)
    governance_suppressed = (state.get("governance_verdict", {}).get("verdict") == "suppressed")
    if should_notify and not governance_suppressed:
        logger.info(f"Routing to voice_synthesis: should_notify={should_notify}, governance_suppressed={governance_suppressed}")
        return "voice_synthesis"
    logger.info(f"Routing to trace_compilation: should_notify={should_notify}, governance_suppressed={governance_suppressed}")
    return "trace_compilation"


def get_opportunity_graph():
    """Lazy-load the compiled graph (imports langgraph only on first access)."""
    global _opportunity_graph
    if _opportunity_graph is None:
        _opportunity_graph = build_opportunity_graph()
    return _opportunity_graph


# ── Node Functions ───────────────────────────────────────────────────

@trace_async("retrieve_candidate_context")
async def _retrieve_candidate_context(state: dict) -> dict:
    """Retrieve candidate profile + resume chunks from Qdrant via semantic search."""
    user_id = state.get("user_id", "unknown")
    try:
        from src.agents.opportunity_discovery_agent import get_opportunity_discovery_agent
        agent = get_opportunity_discovery_agent()
        discovery = await agent.discover(user_id, candidate_context=state.get("candidate_context"))
        provided_opportunities = state.get("opportunities") or []
        merged_opportunities: list[dict] = []
        provided_index: dict[str, dict] = {}
        for opp in provided_opportunities:
            if not isinstance(opp, dict):
                continue
            key = str(opp.get("source_job_id") or opp.get("job_uid") or opp.get("id") or "").strip()
            if key:
                provided_index[key] = opp
        for opp in discovery.discovered_opportunities:
            if not isinstance(opp, dict):
                merged_opportunities.append(opp)
                continue
            key = str(opp.get("source_job_id") or opp.get("job_uid") or opp.get("id") or "").strip()
            merged = dict(opp)
            provided = provided_index.get(key)
            if provided:
                for field, value in provided.items():
                    if value not in (None, "", [], {}):
                        merged[field] = value
            merged_opportunities.append(merged)
        if not merged_opportunities and provided_opportunities:
            merged_opportunities = [opp for opp in provided_opportunities if isinstance(opp, dict)]
        return {
            "current_node": "retrieve_candidate_context",
            "completion_pct": 10.0,
            "candidate_context": state.get("candidate_context", {}) or {},
            "resume_context": discovery.resume_context,
            "market_context": discovery.market_context,
            "opportunities": merged_opportunities or discovery.discovered_opportunities,
        }
    except Exception as e:
        return {
            "current_node": "retrieve_candidate_context",
            "completion_pct": 10.0,
            "candidate_context": state.get("candidate_context", {}) or {},
            "resume_context": {"status": "error", "error": str(e)},
            "market_context": {},
            "opportunities": state.get("opportunities") or [],
        }


@trace_async("retrieve_resume_context")
async def _retrieve_resume_context(state: dict) -> dict:
    """Enrich resume context with structured profile extraction from retrieved chunks."""
    resume_ctx = state.get("resume_context", {})

    # Convert dataclass to plain dict if needed — dataclasses don't unpack with **
    if not isinstance(resume_ctx, dict):
        try:
            from dataclasses import asdict
            resume_ctx = asdict(resume_ctx)
        except Exception:
            resume_ctx = vars(resume_ctx) if hasattr(resume_ctx, '__dict__') else {}

    chunks = resume_ctx.get("resume_chunks", [])
    all_skills = set(resume_ctx.get("skills", []))
    total_chunks = resume_ctx.get("chunk_count", len(chunks))

    # Preserve all original fields — skills, resume_text, education, experience
    return {
        "current_node": "retrieve_resume_context",
        "completion_pct": 20.0,
        "resume_context": {
            **resume_ctx,
            "retrieved": True,
            "chunks_retrieved": total_chunks,
            "skills_aggregated": len(all_skills),
        },
    }


@trace_async("retrieve_market_context")
async def _retrieve_market_context(state: dict) -> dict:
    from src.services.opportunity.market_signal_engine import get_market_signal_engine
    engine = get_market_signal_engine()
    signals = engine.get_signals()
    return {
        "current_node": "retrieve_market_context",
        "completion_pct": 30.0,
        "market_context": {**(state.get("market_context") or {}), "signals": signals},
    }


@trace_async("evaluate_opportunity_fit")
async def _evaluate_opportunity_fit(state: dict) -> dict:
    from src.services.opportunity.opportunity_match_engine import get_opportunity_match_engine
    engine = get_opportunity_match_engine()
    opps = state.get("opportunities") or []
    candidate = state.get("resume_context") or state.get("candidate_context") or {}
    scored: list = []

    # Fallback: load pre-scored opportunities from DB when discovery returns empty
    if not opps and state.get("user_id"):
        try:
            from src.db.session import async_session
            from sqlalchemy import text
            async with async_session() as db:
                rows = await db.execute(
                    text("SELECT os.opportunity_id, os.overall_score, os.confidence, os.dimension_scores, j.title, j.company FROM opportunity_scores os LEFT JOIN jobs j ON os.opportunity_id = j.id::text WHERE os.user_id = :uid ORDER BY os.overall_score DESC LIMIT 20"),
                    {"uid": state["user_id"]}
                )
                for row in rows.fetchall():
                    scored.append({
                        "opportunity_id": row[0],
                        "overall_score": float(row[1] or 0),
                        "confidence": float(row[2] or 0.5),
                        "dimension_scores": row[3] or {},
                        "title": row[4] or "",
                        "company": row[5] or "",
                    })
                if scored:
                    logger.info(f"Loaded {len(scored)} pre-scored opportunities from DB for user {state['user_id']}")
        except Exception as e:
            logger.warning(f"DB fallback for opportunities failed: {e}")

    # Score against match engine if opportunities available
    for opp in opps:
        result = engine.score(opp, candidate)
        scored.append({
            "opportunity_id": opp.get("id", ""),
            "title": opp.get("title", ""),
            "company": opp.get("company", ""),
            "overall_score": result["overall_score"],
            "confidence": result["confidence"],
            "dimension_scores": result["dimension_scores"],
        })
    # Persist scored opportunities to DB (awaited, not fire-and-forget)
    await _persist_opportunity_scores(
        user_id=state.get("user_id", "unknown"),
        session_uid=state.get("session_uid", ""),
        scored_opportunities=scored,
    )

    return {
        "current_node": "evaluate_opportunity_fit",
        "completion_pct": 50.0,
        "scored_opportunities": scored,
    }


@trace_async("evaluate_urgency")
async def _evaluate_urgency(state: dict) -> dict:
    from src.agents.deadline_urgency_agent import get_deadline_urgency_agent
    agent = get_deadline_urgency_agent()
    urgency_state = await agent.evaluate(
        state.get("user_id", "unknown"),
        state.get("scored_opportunities", []),
    )
    scored = state.get("scored_opportunities", [])
    for opp in scored:
        oid = opp.get("opportunity_id", "")
        opp["urgency_score"] = urgency_state.urgency_scores.get(oid, 0.0)
    return {
        "current_node": "evaluate_urgency",
        "completion_pct": 60.0,
        "scored_opportunities": scored,
    }


@trace_async("generate_priority_score")
async def _generate_priority_score(state: dict) -> dict:
    from src.services.opportunity.prioritization_engine import get_prioritization_engine
    engine = get_prioritization_engine()
    ranked = engine.rank(state.get("scored_opportunities", []))
    return {
        "current_node": "generate_priority_score",
        "completion_pct": 70.0,
        "priority_queue": ranked,
    }


@trace_async("governance_validation")
async def _governance_validation(state: dict) -> dict:
    from src.agents.orchestration_governance_agent import get_orchestration_governance_agent
    agent = get_orchestration_governance_agent()
    queue = state.get("priority_queue", [])
    top = queue[0] if queue else {}
    gov_state = await agent.validate(
        session_uid=state.get("session_uid", ""),
        autonomous_count=state.get("autonomous_count", 0),
        recursion_depth=state.get("recursion_depth", 0),
        action_confidence=top.get("confidence", 0.5),
        action_type="notification",
        opportunity_id=top.get("opportunity_id", ""),
    )
    return {
        "current_node": "governance_validation",
        "completion_pct": 75.0,
        "governance_verdict": {
            "verdict": gov_state.verdict,
            "suppressed_actions": gov_state.suppressed_actions,
            "decisions": gov_state.decisions,
        },
    }


@trace_async("notification_decision")
async def _notification_decision(state: dict) -> dict:
    from src.agents.notification_decision_agent import get_notification_decision_agent
    agent = get_notification_decision_agent()
    queue = state.get("priority_queue", [])
    top = queue[0] if queue else {}
    gov = state.get("governance_verdict", {})
    decision = await agent.decide(
        user_id=state.get("user_id", "unknown"),
        opportunity=top,
        score_data=top,
        urgency=top.get("urgency_score", 0.0),
        governance_passed=gov.get("verdict") != "suppressed",
    )
    logger.info(f"Notification decision: should_notify={decision.should_notify}, "
                f"channel={decision.channel}, reason={decision.suppression_reason}")
    return {
        "current_node": "notification_decision",
        "completion_pct": 80.0,
        "should_notify": decision.should_notify,
        "notification_channel": decision.channel,
        "notification_message": decision.notification_message,
    }


@trace_async("voice_synthesis")
async def _voice_synthesis(state: dict) -> dict:
    queue = state.get("priority_queue", [])
    top = queue[0] if queue else {}

    from src.agents.elevenlabs_voice_synthesis_agent import get_elevenlabs_voice_synthesis_agent
    agent = get_elevenlabs_voice_synthesis_agent()
    synth = await agent.synthesize(
        user_id=state.get("user_id", "unknown"),
        candidate_name=top.get("title", ""),
        job_title=top.get("title", ""),
        company=top.get("company", ""),
        match_score=int(top.get("overall_score", 0)),
        urgency="high",
        notification_message=state.get("notification_message", ""),
    )

    result = {"voice_script": synth.voice_script}
    mcp_log: dict = {}

    if synth.audio_result and synth.audio_result.get("status") not in ("rejected", "failed"):
        from src.services.mcp.mcp_router import get_mcp_router
        router = get_mcp_router()
        mcp_result = await router.dispatch(
            tool_name="generate_audio",
            arguments={
                "candidate_name": top.get("title", "unknown"),
                "job_title": top.get("title", ""),
                "company": top.get("company", ""),
                "match_score": int(top.get("overall_score", 0)),
                "urgency": "high",
            },
            session_uid=state.get("session_uid", ""),
        )
        result = {**result, **mcp_result}
        result["voice_script"] = synth.voice_script
        mcp_log = {
            "tool_name": "generate_audio",
            "server_name": "elevenlabs",
            "status": mcp_result.get("status", "unknown"),
            "duration_ms": mcp_result.get("duration_ms", 0),
        }
        from src.services.mcp.mcp_observability import get_mcp_observability
        obs = get_mcp_observability()
        obs.record_call("generate_audio", mcp_result.get("status", "unknown"),
                        mcp_result.get("duration_ms", 0))

    return {
        "current_node": "voice_synthesis",
        "completion_pct": 90.0,
        "voice_audio_result": result,
        "voice_script": synth.voice_script,
        "mcp_voicesynthesis_log": mcp_log,
    }


@trace_async("twilio_call_execution")
async def _twilio_call_execution(state: dict) -> dict:
    from src.services.mcp.mcp_router import get_mcp_router
    router = get_mcp_router()
    audio = state.get("voice_audio_result", {})
    audio_ref = audio.get("audio_asset_reference", "") or audio.get("voice_script", "default.mp3")
    phone = state.get("phone_number") or state.get("candidate_context", {}).get("phone_number", "")

    result = await router.dispatch(
        tool_name="make_call",
        arguments={
            "phone_number": phone,
            "audio_message": audio_ref,
        },
        session_uid=state.get("session_uid", ""),
    )

    from src.services.mcp.mcp_observability import get_mcp_observability
    obs = get_mcp_observability()
    obs.record_call("make_call", result.get("status", "unknown"),
                    result.get("duration_ms", 0))

    return {
        "current_node": "twilio_call_execution",
        "completion_pct": 95.0,
        "twilio_call_result": result,
        "mcp_twilio_log": {
            "tool_name": "make_call",
            "server_name": "twilio",
            "status": result.get("status", "unknown"),
            "duration_ms": result.get("duration_ms", 0),
        },
    }


@trace_async("trace_compilation")
async def _trace_compilation(state: dict) -> dict:
    from src.agents.explainability_agent import get_explainability_agent
    agent = get_explainability_agent()
    queue = state.get("priority_queue", [])
    top = queue[0] if queue else {}

    notification_sent = state.get("should_notify", False) and \
        state.get("governance_verdict", {}).get("verdict", "") != "suppressed"

    result = await agent.compile(
        session_uid=state.get("session_uid", ""),
        action_data={
            "action_id": f"action_{state.get('session_uid', 'default')}",
            "action_type": "opportunity_notification",
            "should_notify": notification_sent,
            "channel": state.get("notification_channel", "voice"),
            "notification_message": state.get("notification_message", ""),
            "confidence": top.get("confidence", 0.5),
            "urgency": top.get("urgency_score", 0.0),
        },
        scoring_context={
            "overall_score": top.get("overall_score", 0),
            "confidence": top.get("confidence", 0.5),
            "dimension_scores": top.get("dimension_scores", {}),
        },
        urgency_context={"urgency_score": top.get("urgency_score", 0.0)},
        governance_context=state.get("governance_verdict", {}),
    )
    return {
        "current_node": "trace_compilation",
        "completion_pct": 100.0,
        "status": "completed",
        "explainability_output": result.final_explanation,
        "trace": {
            "session_uid": state.get("session_uid", ""),
            "nodes_executed": [
                "retrieve_candidate_context", "retrieve_resume_context",
                "retrieve_market_context", "evaluate_opportunity_fit",
                "evaluate_urgency", "generate_priority_score",
                "governance_validation", "notification_decision",
                "voice_synthesis" if notification_sent else "skipped_voice",
                "twilio_call_execution" if notification_sent else "skipped_twilio",
                "trace_compilation",
            ],
            "explainability": result.final_explanation,
            "total_opportunities": len(state.get("scored_opportunities", [])),
            "notification_sent": notification_sent,
            "mcp_voicesynthesis_log": state.get("mcp_voicesynthesis_log"),
            "mcp_twilio_log": state.get("mcp_twilio_log"),
            "errors": state.get("errors", []),
        },
    }

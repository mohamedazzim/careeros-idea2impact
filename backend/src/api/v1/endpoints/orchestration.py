"""Phase 5/6 — Orchestration API Endpoints (hardened).

Phase 17.9: Uses OrchestrationSessionRepository + GovernanceDecisionRepository
+ AutonomousActionRepository. No in-memory _sessions dict. No raw SQL.
"""

import uuid
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.db.repositories.domain_repositories import (
    OrchestrationSessionRepository,
    OrchestrationEventRepository,
    GovernanceDecisionRepository,
    AutonomousActionRepository,
    MCPExecutionLogRepository,
)
from src.api.deps import get_current_user_id
from src.observability.metrics import ORCHESTRATION_FAILURES, ORCHESTRATION_SESSION_GAUGE

router = APIRouter(prefix="/orchestration", tags=["Orchestration"])
logger = logging.getLogger(__name__)


class OrchestrationTriggerRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="Deprecated — extracted from JWT")
    candidate_context: Dict[str, Any] = Field(default_factory=dict)
    opportunities: List[Dict[str, Any]] = Field(default_factory=list)
    phone_number: Optional[str] = Field(None)
    auto_execute: bool = Field(False)


@router.post("/trigger")
async def trigger_orchestration(
    request: OrchestrationTriggerRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Trigger a new orchestration run."""
    repo = OrchestrationSessionRepository(db)
    session_uid = str(uuid.uuid4())

    session = await repo.create(
        session_uid=session_uid,
        user_id=user_id,
        graph_name="opportunity_graph",
        status="active",
        current_node="initialized",
        completion_pct=0.0,
        metadata_={
            "candidate_context": request.candidate_context,
            "opportunities": request.opportunities,
            "phone_number": request.phone_number,
        },
    )
    event_repo = OrchestrationEventRepository(db)
    await _record_event(
        event_repo,
        session_id=session.id,
        event_type="session_started",
        node_name="initialized",
        agent_name="orchestration_api",
        payload={
            "session_uid": session_uid,
            "opportunity_count": len(request.opportunities),
            "phone_number_present": bool(request.phone_number),
            "auto_execute": request.auto_execute,
        },
        status="completed",
    )

    _cache_session(session_uid, {"status": "active", "current_node": "initialized", "completion_pct": 0.0, "user_id": user_id})

    async def _run_graph_background(session_id: int, session_uid: str, uid: str):
        from src.db.session import async_session as _as
        try:
            from src.graphs.opportunity_graph import get_opportunity_graph
            graph = get_opportunity_graph()
            config = {"configurable": {"thread_id": session_uid}}
            initial_state = {
                "session_uid": session_uid,
                "user_id": uid,
                "candidate_context": request.candidate_context,
                "opportunities": request.opportunities,
                "phone_number": request.phone_number,
            }
            result = await graph.ainvoke(initial_state, config)

            async with _as() as _db:
                _repo = OrchestrationSessionRepository(_db)
                _event_repo = OrchestrationEventRepository(_db)
                await _record_event(
                    _event_repo,
                    session_id=session_id,
                    event_type="graph_completed",
                    node_name=result.get("current_node", "unknown") if isinstance(result, dict) else "unknown",
                    agent_name="opportunity_graph",
                    payload={
                        "status": "completed",
                        "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
                        "has_errors": bool(result.get("errors")) if isinstance(result, dict) else False,
                    },
                    status="completed",
                )

                # Persist governance decisions, autonomous actions, and MCP execution logs
                try:
                    gdr = GovernanceDecisionRepository(_db)
                    gov_data = result.get("governance_verdict", {}) if isinstance(result, dict) else {}
                    priority_q = result.get("priority_queue", []) if isinstance(result, dict) else []
                    top_confidence = priority_q[0].get("confidence", 0.5) if priority_q else 0.5
                    should_notify = result.get("should_notify", False) if isinstance(result, dict) else False
                    await gdr.create(
                        session_id=session_id,
                        decision_type="notification",
                        verdict=gov_data.get("verdict", "passed") if isinstance(gov_data, dict) else "passed",
                        confidence_before=gov_data.get("confidence_before", top_confidence) if isinstance(gov_data, dict) else top_confidence,
                        confidence_after=gov_data.get("confidence_after", top_confidence) if isinstance(gov_data, dict) else top_confidence,
                        penalty_applied=gov_data.get("penalty_applied", 0.0) if isinstance(gov_data, dict) else 0.0,
                        reason=str(gov_data.get("decisions", [])) if isinstance(gov_data, dict) else "",
                    )
                    ar = AutonomousActionRepository(_db)
                    action_type = "voice_call" if should_notify else "evaluation"
                    await ar.create(
                        action_uid=f"action_{session_uid}",
                        session_id=session_id,
                        user_id=uid,
                        action_type=action_type,
                        status="completed",
                        confidence=top_confidence,
                        reasoning_chain=[result.get("explainability_output", "") if isinstance(result, dict) else ""],
                        evidence_chain=result.get("explainability_output", "") if isinstance(result, dict) else "",
                        governance_verdict=gov_data.get("verdict", "passed") if isinstance(gov_data, dict) else "passed",
                        mcp_tool_used=("twilio.make_call" if should_notify else None),
                        trace_id=session_uid,
                    )

                    # Persist MCP execution logs from graph results
                    persisted_mcp_count = 0
                    if isinstance(result, dict):
                        mcp_logs: list = []
                        vs_log = result.get("mcp_voicesynthesis_log")
                        tw_log = result.get("mcp_twilio_log")
                        if vs_log and isinstance(vs_log, dict) and vs_log.get("tool_name"):
                            mcp_logs.append(vs_log)
                        if tw_log and isinstance(tw_log, dict) and tw_log.get("tool_name"):
                            mcp_logs.append(tw_log)
                        if mcp_logs:
                            mcp_repo = MCPExecutionLogRepository(_db)
                            for mlog in mcp_logs:
                                await mcp_repo.create(
                                    session_id=session_id,
                                    tool_name=mlog.get("tool_name", "unknown"),
                                    server_name=mlog.get("server_name", "unknown"),
                                    status=mlog.get("status", "unknown"),
                                    attempt=1,
                                    duration_ms=mlog.get("duration_ms"),
                                    trace_id=session_uid,
                                )
                            persisted_mcp_count = len(mcp_logs)

                    await _record_event(
                        _event_repo,
                        session_id=session_id,
                        event_type="artifacts_persisted",
                        node_name="persistence",
                        agent_name="orchestration_api",
                        payload={"governance_decision": True, "autonomous_action": True, "mcp_execution_logs": len(mcp_logs) if 'mcp_logs' in dir() else 0},
                        status="completed",
                    )
                except Exception as ex:
                    logger.warning(f"Failed to persist orchestration artifacts: {ex}")

                await _repo.update(session_id, status="success", completion_pct=100.0, current_node="end",
                                  errors=result.get("errors") if isinstance(result, dict) else None)
                await _record_event(
                    _event_repo,
                    session_id=session_id,
                    event_type="session_completed",
                    node_name="end",
                    agent_name="orchestration_api",
                    payload={
                        "status": "success",
                        "completion_pct": 100.0,
                        "error_count": len(result.get("errors", [])) if isinstance(result, dict) and isinstance(result.get("errors"), list) else 0,
                    },
                    status="completed",
                )
                _cache_session(session_uid, {"status": "success", "completion_pct": 100.0, "current_node": "end"})
        except Exception as exc:
            ORCHESTRATION_FAILURES.labels(node_name="trigger", reason="exception").inc()
            async with _as() as _db:
                _repo = OrchestrationSessionRepository(_db)
                _event_repo = OrchestrationEventRepository(_db)
                await _repo.update(session_id, status="failed", errors={"message": str(exc)})
                await _record_event(
                    _event_repo,
                    session_id=session_id,
                    event_type="session_failed",
                    node_name="trigger",
                    agent_name="orchestration_api",
                    payload={"error": str(exc)},
                    status="failed",
                )
            _cache_session(session_uid, {"status": "failed", "current_node": "initialized", "completion_pct": 0.0})

    asyncio.create_task(_run_graph_background(session.id, session_uid, user_id))

    return {"session_uid": session_uid, "status": "active", "current_node": "initialized", "completion_pct": 0.0}


@router.get("/status/{session_uid}")
async def orchestration_status(session_uid: str, db: AsyncSession = Depends(get_db)):
    """Get current status of an orchestration session."""
    repo = OrchestrationSessionRepository(db)
    session = await repo.get_by_uid(session_uid)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_uid} not found")
    return {
        "session_uid": session.session_uid,
        "status": session.status or "unknown",
        "current_node": session.current_node or "unknown",
        "completion_pct": session.completion_pct,
        "started_at": session.created_at.isoformat() if session.created_at else None,
        "errors": session.errors or {},
    }


@router.get("/history")
async def orchestration_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """List past orchestration sessions for the authenticated user."""
    repo = OrchestrationSessionRepository(db)
    sessions, total = await repo.find_by_user(user_id, limit=limit, offset=offset)
    return {
        "sessions": [{
            "session_uid": s.session_uid,
            "status": s.status,
            "current_node": s.current_node,
            "completion_pct": s.completion_pct,
            "started_at": s.created_at.isoformat() if s.created_at else None,
            "user_id": s.user_id,
        } for s in sessions],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/cancel/{session_uid}")
async def cancel_orchestration(session_uid: str, db: AsyncSession = Depends(get_db)):
    """Cancel an active orchestration session."""
    repo = OrchestrationSessionRepository(db)
    session = await repo.get_by_uid(session_uid)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "active":
        raise HTTPException(status_code=400, detail="Only active sessions can be cancelled")
    await repo.update(session.id, status="cancelled")
    await _record_event(
        OrchestrationEventRepository(db),
        session_id=session.id,
        event_type="session_cancelled",
        node_name=session.current_node or "unknown",
        agent_name="orchestration_api",
        payload={"session_uid": session_uid},
        status="cancelled",
    )
    return {"session_uid": session_uid, "status": "cancelled"}


class ResumeResponse(BaseModel):
    session_uid: str
    status: str
    current_node: str
    completion_pct: float
    resumed_from: str = ""


@router.post("/resume/{session_uid}", response_model=ResumeResponse)
async def resume_orchestration(
    session_uid: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Resume an orchestration session from its last checkpoint."""
    repo = OrchestrationSessionRepository(db)
    session = await repo.get_by_uid(session_uid)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_uid} not found")

    from src.graphs.opportunity_graph import get_opportunity_graph
    from src.services.checkpoint import get_checkpoint_saver

    saver = get_checkpoint_saver()
    config = {"configurable": {"thread_id": session_uid}}

    # Find the last checkpoint
    last_checkpoint = None
    async for ct in saver.alist(config, limit=1):
        last_checkpoint = ct
        break

    if not last_checkpoint:
        raise HTTPException(status_code=404, detail=f"No checkpoint found for session {session_uid}")

    # Determine the last completed node
    metadata = last_checkpoint.metadata
    resumed_from = metadata.get("source", "unknown") if metadata else "unknown"

    async def _resume_graph(sid: int, uid: str):
        from src.db.session import async_session as _as
        try:
            graph = get_opportunity_graph()
            # Continue execution from last checkpoint — null input means "resume"
            result = await graph.ainvoke(None, config)

            async with _as() as _db2:
                _repo = OrchestrationSessionRepository(_db2)
                current_node = result.get("current_node", "end") if isinstance(result, dict) else "end"
                cpct = result.get("completion_pct", 100.0) if isinstance(result, dict) else 100.0
                await _repo.update(sid, status="success", completion_pct=cpct, current_node=current_node)
                _cache_session(session_uid, {"status": "success", "completion_pct": cpct, "current_node": current_node})
        except Exception as exc:
            async with _as() as _db2:
                _repo = OrchestrationSessionRepository(_db2)
                await _repo.update(sid, status="failed", errors={"message": str(exc)})
                _cache_session(session_uid, {"status": "failed"})

    asyncio.create_task(_resume_graph(session.id, user_id))

    return {
        "session_uid": session_uid,
        "status": "active",
        "current_node": resumed_from,
        "completion_pct": session.completion_pct or 0.0,
        "resumed_from": resumed_from,
    }


@router.get("/governance/decisions")
async def governance_decisions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List governance decisions from orchestration runs."""
    repo = GovernanceDecisionRepository(db)
    decisions, total = await repo.find_recent(limit=limit, offset=offset)
    return {
        "decisions": [{
            "id": d.id, "session_id": d.session_id, "decision_type": d.decision_type,
            "verdict": d.verdict, "rule_violated": d.rule_violated,
            "confidence_before": d.confidence_before, "confidence_after": d.confidence_after,
            "penalty_applied": d.penalty_applied, "reason": d.reason,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        } for d in decisions],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/governance/stats")
async def governance_stats(db: AsyncSession = Depends(get_db)):
    """Governance statistics."""
    repo = GovernanceDecisionRepository(db)
    stats = await repo.get_stats()
    actions, _ = await AutonomousActionRepository(db).find_recent(limit=1)
    return {
        "total_decisions": stats["total"], "passed": stats["passed"], "suppressed": stats["suppressed"],
        "autonomous_actions": {"total": len(actions), "suppressed": sum(1 for a in actions if a.suppressed)},
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/traces")
async def orchestration_traces(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List explainability traces."""
    repo = AutonomousActionRepository(db)
    actions, total = await repo.find_recent(limit=limit, offset=offset)
    return {
        "traces": [{
            "action_uid": a.action_uid, "action_type": a.action_type, "status": a.status,
            "confidence": a.confidence, "reasoning_chain": a.reasoning_chain,
            "evidence_chain": a.evidence_chain, "governance_verdict": a.governance_verdict,
            "suppressed": a.suppressed, "suppression_reason": a.suppression_reason,
            "trace_id": a.trace_id, "created_at": a.created_at.isoformat() if a.created_at else None,
        } for a in actions],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/health")
async def orchestration_health(db: AsyncSession = Depends(get_db)):
    """Runtime health check for orchestration subsystem."""
    try:
        from src.graphs.opportunity_graph import get_opportunity_graph
        graph = get_opportunity_graph()
        graph_ok = graph is not None
    except Exception:
        graph_ok = False
    try:
        from src.db.redis import redis_client
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    repo = OrchestrationSessionRepository(db)
    active = await repo.count()
    return {
        "orchestration": "available", "graph_compiled": graph_ok,
        "redis_connected": redis_ok, "active_sessions": active,
        "timestamp": datetime.utcnow().isoformat(),
    }


def _cache_session(session_uid: str, data: Dict[str, Any]) -> None:
    """Optional Redis cache sidecar for runtime hot state."""
    try:
        import asyncio as _asyncio
        from src.db.redis import redis_client as _rc
        key = f"orch:session:{session_uid}"
        _asyncio.create_task(_rc.setex(key, 7200, json.dumps(data, default=str)))
        ORCHESTRATION_SESSION_GAUGE.set(1)
    except Exception:
        pass


async def _record_event(
    repo: OrchestrationEventRepository,
    *,
    session_id: int,
    event_type: str,
    node_name: Optional[str],
    agent_name: Optional[str],
    payload: Optional[Dict[str, Any]],
    status: str = "completed",
    duration_ms: Optional[int] = None,
) -> None:
    await repo.create(
        event_uid=str(uuid.uuid4()),
        session_id=session_id,
        event_type=event_type,
        node_name=node_name,
        agent_name=agent_name,
        payload=payload,
        status=status,
        duration_ms=duration_ms,
    )

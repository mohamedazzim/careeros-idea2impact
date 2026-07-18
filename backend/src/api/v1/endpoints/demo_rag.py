"""Docs RAG chatbot endpoints for mentor/HR questions."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.deps import get_current_user
from src.services.rag import (
    DemoRagChatRequest,
    DemoRagChatResponse,
    DemoRagError,
    DemoRagHealthResponse,
    DemoRagIndexResponse,
    DemoRagGoldenQuestion,
    RagQuestionRejected,
    get_demo_rag_service,
)
from src.services.security.ai_security import ai_security

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/demo-rag", tags=["Demo RAG"])


@router.post("/chat", response_model=DemoRagChatResponse)
async def demo_rag_chat(request: DemoRagChatRequest) -> DemoRagChatResponse:
    start = time.monotonic()
    service = get_demo_rag_service()
    try:
        response = await service.chat(request)
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        logger.info(
            "demo_rag_chat",
            extra={
                "session_id": request.session_id,
                "viewer_role": request.viewer_role,
                "question_preview": ai_security.redact_pii(request.question[:160]),
                "status": response.status,
                "latency_ms": elapsed_ms,
                "confidence": response.confidence,
                "citation_count": len(response.citations),
            },
        )
        return response
    except RagQuestionRejected as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from exc
    except HTTPException:
        raise
    except Exception as exc:
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        logger.exception(
            "demo_rag_chat_failed",
            extra={
                "session_id": request.session_id,
                "viewer_role": request.viewer_role,
                "question_preview": ai_security.redact_pii(request.question[:160]),
                "latency_ms": elapsed_ms,
            },
        )
        return DemoRagChatResponse(
            status="error",
            answer="Needs verification: the docs chatbot could not complete the request.",
            confidence=0.0,
            citations=[],
            follow_up_questions=[],
            needs_verification=True,
            error=DemoRagError(code="RAG_CHAT_FAILED", message=str(exc)),
        )


@router.post("/index", response_model=DemoRagIndexResponse, dependencies=[Depends(get_current_user)])
async def demo_rag_index(recreate: bool = Query(False)) -> DemoRagIndexResponse:
    service = get_demo_rag_service()
    return await service.index_docs(recreate=recreate)


@router.get("/health", response_model=DemoRagHealthResponse)
async def demo_rag_health() -> DemoRagHealthResponse:
    service = get_demo_rag_service()
    return await service.health()


@router.get("/golden-questions")
async def demo_rag_golden_questions() -> Dict[str, Any]:
    service = get_demo_rag_service()
    questions = await service.golden_questions()
    return {
        "status": "ok",
        "collection": service.collection_name,
        "questions": [q.model_dump() for q in questions],
    }

from __future__ import annotations

import hashlib
import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import httpx
from pydantic import BaseModel, Field
from qdrant_client.models import PointStruct

from src.core.config import settings
from src.services.embedding.embedding_service import get_embedding_service
from src.services.llm.factory import get_llm_provider
from src.services.security.ai_security import ai_security
from src.services.vector_store.qdrant_service import get_qdrant_service

logger = logging.getLogger(__name__)

QUESTION_MAX_LENGTH = 1000
DEFAULT_TOP_K = 6
DEFAULT_SCORE_THRESHOLD = 0.25
MAX_CONTEXT_CHARS = 12_000
MAKE_TIMEOUT_SECONDS = 25.0
MIN_CHAT_TIMEOUT_SECONDS = 5.0
MIN_STAGE_TIMEOUT_SECONDS = 3.0
DOCS_DIR_NAME = "docs"
RAG_DIR_NAME = "rag"

SECRET_SEEKING_PATTERNS = (
    "api key",
    "apikey",
    "secret",
    "token",
    "password",
    "jwt",
    "private key",
    "credentials",
    "credential",
    "cookie",
    "bearer",
    "client secret",
)

ANSWER_FOLLOW_UPS = [
    "Which implementation area do you want to inspect next?",
    "Do you want the backend, frontend, or workflow view of this feature?",
    "Should I summarize the related source files as well?",
]

GOLDEN_QUESTIONS_FILE = "GOLDEN_QUESTIONS.md"


class DemoRagChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    question: str = Field(..., min_length=1, max_length=QUESTION_MAX_LENGTH)
    viewer_role: str = Field("mentor", min_length=1, max_length=32)
    top_k: int = Field(DEFAULT_TOP_K, ge=1, le=12)


class DemoRagCitation(BaseModel):
    doc_name: str
    section_title: str
    source_path: str
    score: float


class DemoRagError(BaseModel):
    code: str
    message: str


class DemoRagChatResponse(BaseModel):
    status: str = "ok"
    answer: str = ""
    confidence: float = 0.0
    citations: List[DemoRagCitation] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    needs_verification: bool = False
    error: Optional[DemoRagError] = None


class DemoRagIndexResponse(BaseModel):
    status: str = "ok"
    files_indexed: int = 0
    chunks_indexed: int = 0
    successful_upserts: int = 0
    failed_chunks: int = 0
    collection: str
    source_path: str


class DemoRagHealthResponse(BaseModel):
    status: str = "ok"
    collection: str
    docs_path: str
    files_found: int
    chunks_known: int
    qdrant_ready: bool
    qdrant_collection_ready: bool
    embedding_model: str
    llm_model: str
    make_enabled: bool
    last_indexed_at: Optional[str] = None


class DemoRagGoldenQuestion(BaseModel):
    question: str
    expected_source_file: str
    expected_answer_type: str
    must_mention: List[str] = Field(default_factory=list)
    should_not_mention: List[str] = Field(default_factory=list)


class RagQuestionRejected(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class RagChunk:
    chunk_id: str
    doc_name: str
    section_title: str
    source_path: str
    chunk_index: int
    updated_at: str
    content_hash: str
    text: str
    source: str = "docs/rag"

    def to_payload(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_name": self.doc_name,
            "section_title": self.section_title,
            "source_path": self.source_path,
            "chunk_index": self.chunk_index,
            "updated_at": self.updated_at,
            "content_hash": self.content_hash,
            "text": self.text,
            "source": self.source,
        }


class RagRetrievalHit(BaseModel):
    chunk_id: str
    doc_name: str
    section_title: str
    source_path: str
    score: float
    text: str
    chunk_index: int
    updated_at: str


class RagRetrievalResult(BaseModel):
    status: str
    reason: str = ""
    top_score: float = 0.0
    chunks: List[RagRetrievalHit] = Field(default_factory=list)


class RagLLMOutput(BaseModel):
    answer: str = ""
    confidence: float = 0.0
    citation_ids: List[int] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    needs_verification: bool = False


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / DOCS_DIR_NAME / RAG_DIR_NAME).exists():
            return parent
    return current.parents[4] if len(current.parents) > 4 else current.parent


def _docs_root() -> Path:
    return _repo_root() / DOCS_DIR_NAME / RAG_DIR_NAME


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _make_chunk_id(source_path: str, section_title: str, content_hash: str) -> str:
    digest = hashlib.sha256(f"{source_path}|{section_title}|{content_hash}".encode("utf-8")).hexdigest()
    return f"rag-{digest[:24]}"


def _split_long_section(text: str, max_chars: int = 2800) -> List[str]:
    clean = text.strip()
    if len(clean) <= max_chars:
        return [clean]

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean) if p.strip()]
    if not paragraphs:
        paragraphs = [clean]

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        if current and current_len + paragraph_len + 2 > max_chars:
            chunks.append("\n\n".join(current).strip())
            current = [paragraph]
            current_len = paragraph_len
        else:
            current.append(paragraph)
            current_len += paragraph_len + 2
    if current:
        chunks.append("\n\n".join(current).strip())

    if not chunks:
        return [clean[i : i + max_chars] for i in range(0, len(clean), max_chars)]

    final_chunks: List[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            final_chunks.extend([chunk[i : i + max_chars] for i in range(0, len(chunk), max_chars)])
    return [chunk for chunk in final_chunks if chunk.strip()]


def _sanitize_for_logging(text: str, max_len: int = 160) -> str:
    clean = ai_security.redact_pii(text).replace("\n", " ").strip()
    return clean[:max_len]


class DemoRagService:
    def __init__(self) -> None:
        self.collection_name = settings.QDRANT_RAG_DOCS_COLLECTION
        self.docs_path = _docs_root()

    def _discover_markdown_files(self) -> List[Path]:
        if not self.docs_path.exists():
            return []
        return sorted(
            path for path in self.docs_path.rglob("*.md")
            if path.is_file()
        )

    def _parse_markdown(self, source_path: Path, text: str) -> List[RagChunk]:
        normalized = _normalize_text(text)
        if not normalized:
            return []

        lines = normalized.splitlines()
        heading_pattern = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
        heading_stack: List[tuple[int, str]] = []
        current_lines: List[str] = []
        chunks: List[RagChunk] = []
        chunk_index = 0
        updated_at = datetime.fromtimestamp(source_path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat()

        def flush_section() -> None:
            nonlocal chunk_index, current_lines
            content = "\n".join(current_lines).strip()
            if not content:
                current_lines = []
                return
            section_title = " > ".join(title for _, title in heading_stack) if heading_stack else source_path.stem
            content_hash = _short_hash(content)
            for part_index, part in enumerate(_split_long_section(content)):
                part_hash = _short_hash(f"{content_hash}|{part_index}|{part}")
                chunk_id = _make_chunk_id(str(source_path.relative_to(_repo_root())), section_title, part_hash)
                chunks.append(
                    RagChunk(
                        chunk_id=chunk_id,
                        doc_name=source_path.name,
                        section_title=section_title,
                        source_path=str(source_path.relative_to(_repo_root())).replace("\\", "/"),
                        chunk_index=chunk_index,
                        updated_at=updated_at,
                        content_hash=part_hash,
                        text=part,
                    )
                )
                chunk_index += 1
            current_lines = []

        for line in lines:
            heading_match = heading_pattern.match(line)
            if heading_match:
                flush_section()
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))
                current_lines = [line]
            else:
                current_lines.append(line)

        flush_section()
        return chunks

    async def index_docs(self, recreate: bool = False) -> DemoRagIndexResponse:
        files = self._discover_markdown_files()
        qdrant_service = get_qdrant_service()
        if recreate:
            await qdrant_service.recreate_collection(self.collection_name)
        else:
            await qdrant_service.init_collections()

        all_chunks: List[RagChunk] = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="ignore")
            all_chunks.extend(self._parse_markdown(path, text))

        if not all_chunks:
            return DemoRagIndexResponse(
                collection=self.collection_name,
                source_path=str(self.docs_path.relative_to(_repo_root())).replace("\\", "/") if self.docs_path.exists() else "docs/rag",
            )

        embedder = get_embedding_service()
        vectors = await embedder.generate_embeddings([chunk.text for chunk in all_chunks], input_type="passage")

        points: List[PointStruct] = []
        failed_chunks = 0
        for chunk, vector in zip(all_chunks, vectors):
            if not vector or len(vector) != embedder.dimensions:
                failed_chunks += 1
                continue
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                    vector=vector,
                    payload=chunk.to_payload(),
                )
            )

        upserted = 0
        if points:
            upserted = await qdrant_service.upsert_points(self.collection_name, points)

        logger.info(
            "Indexed docs RAG collection",
            extra={
                "collection": self.collection_name,
                "files_indexed": len(files),
                "chunks_indexed": len(all_chunks),
                "successful_upserts": upserted,
                "failed_chunks": failed_chunks,
            },
        )

        return DemoRagIndexResponse(
            collection=self.collection_name,
            source_path=str(self.docs_path.relative_to(_repo_root())).replace("\\", "/") if self.docs_path.exists() else "docs/rag",
            files_indexed=len(files),
            chunks_indexed=len(all_chunks),
            successful_upserts=upserted,
            failed_chunks=failed_chunks,
        )

    def validate_question(self, question: str) -> str:
        normalized = question.strip()
        if not normalized:
            raise RagQuestionRejected("EMPTY_QUESTION", "Question cannot be empty.")
        if len(normalized) > QUESTION_MAX_LENGTH:
            raise RagQuestionRejected("QUESTION_TOO_LONG", f"Question must be {QUESTION_MAX_LENGTH} characters or fewer.")
        try:
            ai_security.validate_prompt_injection(normalized)
        except ValueError as exc:
            raise RagQuestionRejected("PROMPT_INJECTION", str(exc)) from exc
        lowered = normalized.lower()
        if any(pattern in lowered for pattern in SECRET_SEEKING_PATTERNS):
            raise RagQuestionRejected(
                "SECRET_SEEKING",
                "Questions about secrets, credentials, or tokens are not allowed.",
            )
        return normalized

    async def retrieve(self, question: str, top_k: int = DEFAULT_TOP_K) -> RagRetrievalResult:
        normalized = self.validate_question(question)
        embedder = get_embedding_service()
        query_vector = await embedder.embed_query(normalized)
        if not query_vector:
            return RagRetrievalResult(status="NO_RELEVANT_CONTEXT", reason="EMPTY_EMBEDDING")

        qdrant_service = get_qdrant_service()
        await qdrant_service.init_collections()
        scored_points = await qdrant_service.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=DEFAULT_SCORE_THRESHOLD,
        )

        hits: List[RagRetrievalHit] = []
        for point in scored_points:
            payload = point.payload or {}
            hits.append(
                RagRetrievalHit(
                    chunk_id=str(payload.get("chunk_id") or point.id),
                    doc_name=str(payload.get("doc_name") or ""),
                    section_title=str(payload.get("section_title") or ""),
                    source_path=str(payload.get("source_path") or ""),
                    score=float(point.score or 0.0),
                    text=str(payload.get("text") or ""),
                    chunk_index=int(payload.get("chunk_index") or 0),
                    updated_at=str(payload.get("updated_at") or ""),
                )
            )

        if not hits:
            return RagRetrievalResult(status="NO_RELEVANT_CONTEXT", reason="NO_RESULTS")

        top_score = max(hit.score for hit in hits)
        if top_score < DEFAULT_SCORE_THRESHOLD:
            return RagRetrievalResult(status="NO_RELEVANT_CONTEXT", reason="LOW_SCORE", top_score=top_score, chunks=hits)

        return RagRetrievalResult(status="OK", top_score=top_score, chunks=hits)

    def _build_context(self, hits: Sequence[RagRetrievalHit]) -> str:
        context_blocks: List[str] = []
        total_len = 0
        for index, hit in enumerate(hits, start=1):
            block = (
                f"[{index}] {hit.doc_name} :: {hit.section_title}\n"
                f"Source: {hit.source_path}\n"
                f"Chunk ID: {hit.chunk_id}\n"
                f"{hit.text.strip()}"
            ).strip()
            if total_len + len(block) > MAX_CONTEXT_CHARS:
                break
            context_blocks.append(block)
            total_len += len(block)
        return "\n\n".join(context_blocks)

    async def _generate_answer(self, question: str, retrieval: RagRetrievalResult, session_id: str, viewer_role: str) -> DemoRagChatResponse:
        if retrieval.status == "NO_RELEVANT_CONTEXT" or not retrieval.chunks:
            return DemoRagChatResponse(
                status="ok",
                answer="Needs verification: I could not find relevant documentation in `docs/rag/` for that question.",
                confidence=0.0,
                citations=[],
                follow_up_questions=list(ANSWER_FOLLOW_UPS),
                needs_verification=True,
            )

        context = self._build_context(retrieval.chunks)
        citation_lookup = {index: hit for index, hit in enumerate(retrieval.chunks, start=1)}
        prompt = {
            "session_id": session_id,
            "viewer_role": viewer_role,
            "question": question,
            "retrieved_context": context,
            "citation_count": len(retrieval.chunks),
            "instructions": [
                "Answer only from the retrieved documentation context.",
                "Return JSON only.",
                "Use citation_ids that refer to the numbered chunks in the context.",
                "If the question is not supported by context, set needs_verification=true and explain that verification is needed.",
            ],
        }

        system_prompt = (
            "You are the CareerOS mentor/HR documentation chatbot. "
            "Answer strictly from retrieved documentation. "
            "Do not invent features, endpoints, or behaviors. "
            "If the docs do not support the answer, say 'Needs verification'. "
            "Keep the response concise, professional, and factual."
        )

        provider = get_llm_provider()
        parsed: Optional[RagLLMOutput] = None
        try:
            llm_timeout_seconds = max(MIN_STAGE_TIMEOUT_SECONDS, float(settings.RAG_LLM_TIMEOUT_SECONDS or 0))
            response = await asyncio.wait_for(
                provider.structured_generate(
                    system_prompt=system_prompt,
                    user_message=json.dumps(prompt, ensure_ascii=False),
                    output_schema=RagLLMOutput,
                    max_tokens=1200,
                    temperature=0.0,
                    cache_key_hint=f"demo-rag:{_short_hash(question)}:{session_id}:{viewer_role}:{len(retrieval.chunks)}",
                ),
                timeout=llm_timeout_seconds,
            )
            parsed = response.get("parsed") if isinstance(response, dict) else None
            if parsed is None and isinstance(response, dict):
                result_value = response.get("result")
                if isinstance(result_value, dict):
                    parsed = RagLLMOutput.model_validate(result_value)
        except Exception as exc:
            logger.warning("RAG answer generation failed, using extractive fallback: %s", exc)

        if parsed is None:
            answer_text = retrieval.chunks[0].text.strip()
            follow_ups = list(ANSWER_FOLLOW_UPS)
            confidence = min(0.85, max(0.35, retrieval.top_score))
            citations = [
                DemoRagCitation(
                    doc_name=retrieval.chunks[0].doc_name,
                    section_title=retrieval.chunks[0].section_title,
                    source_path=retrieval.chunks[0].source_path,
                    score=retrieval.chunks[0].score,
                )
            ]
            return DemoRagChatResponse(
                status="ok",
                answer=answer_text,
                confidence=confidence,
                citations=citations,
                follow_up_questions=follow_ups,
                needs_verification=confidence < 0.6,
            )

        citations: List[DemoRagCitation] = []
        for citation_id in parsed.citation_ids or []:
            hit = citation_lookup.get(int(citation_id))
            if not hit:
                continue
            citations.append(
                DemoRagCitation(
                    doc_name=hit.doc_name,
                    section_title=hit.section_title,
                    source_path=hit.source_path,
                    score=hit.score,
                )
            )
        if not citations and retrieval.chunks:
            hit = retrieval.chunks[0]
            citations.append(
                DemoRagCitation(
                    doc_name=hit.doc_name,
                    section_title=hit.section_title,
                    source_path=hit.source_path,
                    score=hit.score,
                )
            )

        confidence = float(parsed.confidence or retrieval.top_score or 0.0)
        confidence = max(0.0, min(confidence, 1.0))
        needs_verification = bool(parsed.needs_verification or confidence < 0.6 or not citations)

        answer_text = parsed.answer.strip() or "Needs verification: the retrieved documentation did not support a direct answer."
        follow_ups = [q.strip() for q in parsed.follow_up_questions if q.strip()] or list(ANSWER_FOLLOW_UPS)

        return DemoRagChatResponse(
            status="ok",
            answer=answer_text,
            confidence=confidence,
            citations=citations,
            follow_up_questions=follow_ups[:3],
            needs_verification=needs_verification,
        )

    async def _relay_to_make(
        self,
        request: DemoRagChatRequest,
        retrieval: Optional[RagRetrievalResult] = None,
    ) -> Optional[Dict[str, Any]]:
        if not settings.RAG_USE_MAKE or not settings.MAKE_RAG_WEBHOOK_URL:
            return None

        headers = {"Content-Type": "application/json"}
        if settings.MAKE_RAG_API_KEY:
            headers["X-API-Key"] = settings.MAKE_RAG_API_KEY

        payload = request.model_dump()
        payload["source"] = "careeros-demo-rag"

        if retrieval is not None:
            payload["retrieval_status"] = retrieval.status
            payload["retrieval_reason"] = retrieval.reason
            payload["retrieval_top_score"] = retrieval.top_score
            payload["retrieved_context"] = self._build_context(retrieval.chunks)
            payload["retrieved_chunks"] = [
                {
                    "citation_id": index,
                    "chunk_id": hit.chunk_id,
                    "doc_name": hit.doc_name,
                    "section_title": hit.section_title,
                    "source_path": hit.source_path,
                    "score": hit.score,
                    "text": hit.text,
                    "chunk_index": hit.chunk_index,
                    "updated_at": hit.updated_at,
                }
                for index, hit in enumerate(retrieval.chunks, start=1)
            ]

        timeout = httpx.Timeout(MAKE_TIMEOUT_SECONDS, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                settings.MAKE_RAG_WEBHOOK_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else None

    def _normalize_response(self, payload: Dict[str, Any]) -> DemoRagChatResponse:
        citations_raw = payload.get("citations") or []
        citations: List[DemoRagCitation] = []
        for item in citations_raw:
            if not isinstance(item, dict):
                continue
            citations.append(
                DemoRagCitation(
                    doc_name=str(item.get("doc_name") or item.get("file") or "docs/rag"),
                    section_title=str(item.get("section_title") or item.get("section") or "Unknown section"),
                    source_path=str(item.get("source_path") or item.get("path") or "docs/rag"),
                    score=float(item.get("score") or 0.0),
                )
            )

        follow_ups = [str(q).strip() for q in payload.get("follow_up_questions", []) if str(q).strip()]
        error_value = payload.get("error")
        error = None
        if isinstance(error_value, dict):
            error = DemoRagError(
                code=str(error_value.get("code") or "UPSTREAM_ERROR"),
                message=str(error_value.get("message") or "Make.com returned an error."),
            )

        return DemoRagChatResponse(
            status=str(payload.get("status") or "ok"),
            answer=str(payload.get("answer") or ""),
            confidence=float(payload.get("confidence") or 0.0),
            citations=citations,
            follow_up_questions=follow_ups,
            needs_verification=bool(payload.get("needs_verification") or False),
            error=error,
        )

    async def _chat_impl(self, request: DemoRagChatRequest) -> DemoRagChatResponse:
        validated_question = self.validate_question(request.question)
        normalized_request = request.model_copy(update={"question": validated_question})

        retrieval_timeout_seconds = max(MIN_STAGE_TIMEOUT_SECONDS, float(settings.RAG_RETRIEVAL_TIMEOUT_SECONDS or 0))
        try:
            retrieval = await asyncio.wait_for(
                self.retrieve(validated_question, top_k=normalized_request.top_k),
                timeout=retrieval_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "demo_rag_retrieval_timeout",
                extra={
                    "session_id": normalized_request.session_id,
                    "viewer_role": normalized_request.viewer_role,
                    "timeout_seconds": retrieval_timeout_seconds,
                    "question_preview": _sanitize_for_logging(validated_question),
                },
            )
            return DemoRagChatResponse(
                status="error",
                answer="Needs verification: document retrieval timed out before relevant context could be loaded. Please try again.",
                confidence=0.0,
                citations=[],
                follow_up_questions=[],
                needs_verification=True,
                error=DemoRagError(
                    code="RAG_RETRIEVAL_TIMEOUT",
                    message="Document retrieval timed out before relevant context could be loaded.",
                ),
            )

        make_response: Optional[Dict[str, Any]] = None
        if settings.RAG_USE_MAKE and settings.MAKE_RAG_WEBHOOK_URL:
            try:
                make_response = await self._relay_to_make(normalized_request, retrieval=retrieval)
                if make_response:
                    normalized = self._normalize_response(make_response)
                    if normalized.status == "ok" and normalized.answer.strip():
                        return normalized
            except Exception as exc:
                logger.warning("Make.com relay failed, falling back to local RAG: %s", exc)

        response = await self._generate_answer(
            question=validated_question,
            retrieval=retrieval,
            session_id=normalized_request.session_id,
            viewer_role=normalized_request.viewer_role,
        )
        return response

    async def chat(self, request: DemoRagChatRequest) -> DemoRagChatResponse:
        timeout_seconds = max(MIN_CHAT_TIMEOUT_SECONDS, float(settings.RAG_CHAT_TIMEOUT_SECONDS or 0))
        try:
            return await asyncio.wait_for(self._chat_impl(request), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "demo_rag_chat_timeout",
                extra={
                    "session_id": request.session_id,
                    "viewer_role": request.viewer_role,
                    "timeout_seconds": timeout_seconds,
                    "question_preview": _sanitize_for_logging(request.question),
                },
            )
            return DemoRagChatResponse(
                status="error",
                answer="Needs verification: the docs chatbot timed out before completing the request. Please try again.",
                confidence=0.0,
                citations=[],
                follow_up_questions=[],
                needs_verification=True,
                error=DemoRagError(
                    code="RAG_CHAT_TIMEOUT",
                    message="The docs chatbot timed out before completing the request.",
                ),
            )

    async def health(self) -> DemoRagHealthResponse:
        files = self._discover_markdown_files()
        qdrant_service = get_qdrant_service()
        qdrant_ready = True
        qdrant_collection_ready = False
        chunks_known = 0
        try:
            qdrant_ready = True
            qdrant_collection_ready = await qdrant_service.collection_exists(self.collection_name)
            if qdrant_collection_ready:
                collection_info = await qdrant_service.get_collection_info(self.collection_name)
                chunks_known = int(collection_info.get("points_count") or 0)
        except Exception as exc:
            logger.warning("Docs RAG health check failed: %s", exc)
            qdrant_ready = False

        return DemoRagHealthResponse(
            collection=self.collection_name,
            docs_path=str(self.docs_path.relative_to(_repo_root())).replace("\\", "/") if self.docs_path.exists() else "docs/rag",
            files_found=len(files),
            chunks_known=chunks_known,
            qdrant_ready=qdrant_ready,
            qdrant_collection_ready=qdrant_collection_ready,
            embedding_model=settings.RAG_EMBEDDING_MODEL,
            llm_model=settings.RAG_LLM_MODEL,
            make_enabled=bool(settings.RAG_USE_MAKE and settings.MAKE_RAG_WEBHOOK_URL),
            last_indexed_at=self._latest_docs_timestamp(files),
        )

    def _latest_docs_timestamp(self, files: Sequence[Path]) -> Optional[str]:
        if not files:
            return None
        timestamps = [datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0) for path in files]
        return max(timestamps).isoformat()

    def _parse_golden_questions(self) -> List[DemoRagGoldenQuestion]:
        golden_path = self.docs_path / GOLDEN_QUESTIONS_FILE
        if not golden_path.exists():
            return []

        lines = golden_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        rows: List[DemoRagGoldenQuestion] = []
        in_table = False
        for line in lines:
            if line.strip().startswith("| Question |"):
                in_table = True
                continue
            if not in_table or not line.strip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 5 or cells[0] == "Question":
                continue
            if all(set(cell) <= {"-", " ", "`"} for cell in cells):
                continue
            rows.append(
                DemoRagGoldenQuestion(
                    question=cells[0],
                    expected_source_file=cells[1].strip("`"),
                    expected_answer_type=cells[2],
                    must_mention=[part.strip("` ").strip() for part in cells[3].split(",") if part.strip()],
                    should_not_mention=[part.strip("` ").strip() for part in cells[4].split(",") if part.strip()],
                )
            )
        return rows

    async def golden_questions(self) -> List[DemoRagGoldenQuestion]:
        return self._parse_golden_questions()


_demo_rag_service: Optional[DemoRagService] = None


def get_demo_rag_service() -> DemoRagService:
    global _demo_rag_service
    if _demo_rag_service is None:
        _demo_rag_service = DemoRagService()
    return _demo_rag_service


def reset_demo_rag_service() -> None:
    global _demo_rag_service
    _demo_rag_service = None


def __getattr__(name: str):
    if name == "demo_rag_service":
        return get_demo_rag_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

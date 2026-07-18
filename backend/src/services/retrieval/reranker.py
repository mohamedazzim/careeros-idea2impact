import asyncio
import logging
import time
from typing import List
from langsmith import traceable
import httpx

from src.schemas.retrieval import RetrievedChunk, RerankedChunk
from src.core.config import settings
from src.observability.metrics import (
    RERANK_CIRCUIT_OPEN,
    RERANK_FALLBACK_USED,
    RERANK_TIMEOUT,
    RERANK_RATE_LIMIT,
)

logger = logging.getLogger(__name__)


class RerankerCircuitBreaker:
    """Circuit breaker for reranker API calls."""

    def __init__(self, threshold: int = 3, recovery_timeout: float = 60.0):
        self.threshold = threshold or settings.RERANKER_CIRCUIT_THRESHOLD
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.open = False

    def acquire(self) -> bool:
        if not self.open:
            return True
        if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
            self.open = False
            self.failure_count = 0
            logger.info("Reranker circuit breaker reset to closed")
            return True
        return False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.monotonic()
        if self.failure_count >= self.threshold and not self.open:
            self.open = True
            logger.warning(
                f"Reranker circuit breaker opened after {self.failure_count} failures"
            )

    def record_success(self) -> None:
        if self.open:
            return
        self.failure_count = 0


class RerankerService:
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or settings.NVIDIA_API_KEY or ""
        # NVIDIA reranking lives under the AI Catalog host.
        self.base_url = (base_url or "https://ai.api.nvidia.com/v1").rstrip("/")
        self.rerank_path = "/retrieval/nvidia/reranking"
        self.model_name = "nvidia/rerank-qa-mistral-4b"
        self.max_retries = settings.RERANKER_MAX_RETRIES
        self.retry_base_delay = settings.RERANKER_RETRY_BASE_DELAY
        self.timeout = settings.RERANKER_TIMEOUT
        self.max_batch = settings.RERANKER_MAX_BATCH_SIZE
        self.fallback_strategy = settings.RERANKER_FALLBACK_STRATEGY
        self._circuit = RerankerCircuitBreaker(
            threshold=settings.RERANKER_CIRCUIT_THRESHOLD
        ) if settings.RERANKER_CIRCUIT_BREAKER_ENABLED else None
        self._concurrency = asyncio.Semaphore(3)

    def _build_rerank_url(self) -> str:
        """Build the canonical reranking endpoint URL."""
        return f"{self.base_url}{self.rerank_path}"

    @traceable(name="rerank_chunks")
    async def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_n: int = 5,
    ) -> List[RerankedChunk]:
        """Rerank using rerank-qa-mistral-4b with resilience:
        circuit breaker, retries, timeout, and graceful fallback."""
        if not chunks:
            return []

        # Fall back to score-based mock if no API key
        if not self.api_key:
            logger.warning("NVIDIA_API_KEY not set — falling back to score-based rerank")
            return self._mock_rerank(chunks, top_n)

        # Circuit breaker check
        if self._circuit and not self._circuit.acquire():
            RERANK_CIRCUIT_OPEN.inc()
            RERANK_FALLBACK_USED.labels(strategy="circuit_open").inc()
            logger.warning("Reranker circuit breaker open — using fallback")
            return self._fallback_rerank(query, chunks, top_n)

        # Hard limit: truncate batch if too large
        working_chunks = chunks[:self.max_batch] if len(chunks) > self.max_batch else chunks

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await self._call_api(query, working_chunks, top_n)
                if self._circuit:
                    self._circuit.record_success()
                return result
            except httpx.TimeoutException as e:
                RERANK_TIMEOUT.inc()
                last_exception = e
                logger.warning(
                    f"Reranker timeout (attempt {attempt + 1}/{self.max_retries + 1}): {e}"
                )
            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code == 429:
                    RERANK_RATE_LIMIT.inc()
                    cooldown = 5.0 * (2**attempt)
                    logger.warning(
                        f"Reranker rate limited, waiting {cooldown:.1f}s "
                        f"(attempt {attempt + 1})"
                    )
                    await asyncio.sleep(cooldown)
                else:
                    logger.error(f"Reranker HTTP {e.response.status_code}: {e}")
            except Exception as e:
                last_exception = e
                logger.error(f"Reranker error (attempt {attempt + 1}): {e}")

            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2**attempt)
                await asyncio.sleep(delay)

        # All attempts failed
        if self._circuit:
            self._circuit.record_failure()
        RERANK_FALLBACK_USED.labels(strategy=self.fallback_strategy).inc()
        logger.error(f"Reranker failed after {self.max_retries + 1} attempts, using fallback")
        return self._fallback_rerank(query, chunks, top_n)

    async def _call_api(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_n: int,
    ) -> List[RerankedChunk]:
        """Single rerank API call with configurable timeout."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        texts = [chunk.text for chunk in chunks]
        payload = {
            "model": self.model_name,
            "query": {"text": query},
            "passages": [{"text": txt} for txt in texts],
        }

        url = self._build_rerank_url()
        logger.debug(
            "NVIDIA rerank request",
            extra={
                "provider": "nvidia",
                "method": "POST",
                "url": url,
                "model": self.model_name,
                "passage_count": len(texts),
                "query_chars": len(query),
                "payload_keys": list(payload.keys()),
            },
        )

        async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

            logger.debug(
                "NVIDIA rerank response",
                extra={
                    "provider": "nvidia",
                    "url": url,
                    "status_code": response.status_code,
                    "response_chars": len(response.text or ""),
                },
            )

            response.raise_for_status()
            data = response.json()

            rankings = data.get("rankings", [])
            reranked = []
            for rank in rankings:
                idx = rank["index"]
                score = rank.get("logit", 0.0)
                chunk = chunks[idx]
                reranked.append(
                    RerankedChunk(**chunk.model_dump(), rerank_score=score)
                )

            reranked.sort(key=lambda x: x.rerank_score, reverse=True)
            return reranked[:top_n]

    def _fallback_rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_n: int,
    ) -> List[RerankedChunk]:
        """Graceful degradation: sort by original score.

        Supports 'score_sort' (default), 'skip' (return unmodified), and 'degrade' (score + small boost).
        """
        strategy = self.fallback_strategy

        if strategy == "skip":
            return [
                RerankedChunk(**c.model_dump(), rerank_score=c.score)
                for c in chunks[:top_n]
            ]

        if strategy == "degrade":
            sorted_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)
            return [
                RerankedChunk(
                    **c.model_dump(),
                    rerank_score=c.score * 0.9 + 0.01 / (i + 1),
                )
                for i, c in enumerate(sorted_chunks[:top_n])
            ]

        # Default: score_sort
        return self._mock_rerank(chunks, top_n)

    def _mock_rerank(
        self, chunks: List[RetrievedChunk], top_n: int
    ) -> List[RerankedChunk]:
        sorted_chunks = sorted(chunks, key=lambda x: x.score, reverse=True)
        return [
            RerankedChunk(
                **c.model_dump(),
                rerank_score=c.score + (1.0 / (idx + 1)),
            )
            for idx, c in enumerate(sorted_chunks[:top_n])
        ]

_reranker_service = None


def get_reranker_service() -> RerankerService:
    """Lazily initialize and return the module-level singleton."""
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service


def reset_reranker_service() -> None:
    global _reranker_service
    _reranker_service = None


def __getattr__(name: str):
    if name == "reranker_service":
        return get_reranker_service()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

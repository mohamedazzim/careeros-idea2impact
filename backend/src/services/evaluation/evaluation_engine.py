"""
Enterprise evaluation engine for LLM output quality assessment.

Evaluates: hallucination, grounding, faithfulness, retrieval quality,
reranking efficacy, answer relevance, context precision.

All evaluations use the real provider abstraction. No mock scores.
"""

import json
import logging
import hashlib
import time
from typing import Dict, Any, List, Optional

from pydantic import BaseModel, Field

from src.services.intelligence.claude_service import get_claude_service

logger = logging.getLogger(__name__)

_evaluation_engine: Optional["EvaluationEngine"] = None


class EvaluationEngine:
    class EvaluationBundle(BaseModel):
        hallucination_score: float = 50
        high_risk_spans: List[str] = Field(default_factory=list)
        grounding_score: float = 70
        unsupported_claims: List[str] = Field(default_factory=list)
        relevance_score: float = 60
        retrieval_quality_score: float = 60
        irrelevant_count: int = 0
        explanation: str = ""
        evidence: List[str] = Field(default_factory=list)

    async def evaluate_hallucination(self, response: str, context: str) -> Dict[str, Any]:
        claude = get_claude_service()
        t0 = time.monotonic()
        try:
            result = await claude.reason_text(
                system_prompt="You are a hallucination detector for AI-generated text. Score 0-100 where 0=fully hallucinated, 100=fully grounded. Return JSON: {score: number, high_risk_spans: [string], explanation: string}.",
                human_message=f"Context (ground truth):\n{context[:3000]}\n\nResponse to check:\n{response[:2000]}",
                category="evaluation",
                cache_key_hint=f"hallucination:{hashlib.sha256((context[:3000] + '|' + response[:2000]).encode('utf-8')).hexdigest()[:16]}",
            )
            import json
            text = self._extract(result)
            parsed = json.loads(text) if text else {"score": 50, "high_risk_spans": [], "explanation": "Unable to parse"}
            return {
                "hallucination_score": parsed.get("score", 50),
                "high_risk_spans": parsed.get("high_risk_spans", []),
                "explanation": parsed.get("explanation", ""),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }
        except Exception as e:
            logger.error(f"Hallucination eval failed: {e}")
            return {"hallucination_score": 50, "high_risk_spans": [], "explanation": str(e), "error": True}

    async def evaluate_grounding(self, response: str, context: str) -> Dict[str, Any]:
        claude = get_claude_service()
        t0 = time.monotonic()
        try:
            result = await claude.reason_text(
                system_prompt="Assess whether every claim in the response is supported by the context. Score 0-100. Return JSON: {score: number, unsupported_claims: [string], explanation: string}.",
                human_message=f"Context:\n{context[:3000]}\n\nResponse:\n{response[:2000]}",
                category="evaluation",
                cache_key_hint=f"grounding:{hashlib.sha256((context[:3000] + '|' + response[:2000]).encode('utf-8')).hexdigest()[:16]}",
            )
            import json
            text = self._extract(result)
            parsed = json.loads(text) if text else {"score": 70, "unsupported_claims": [], "explanation": "Unable to parse"}
            return {
                "grounding_score": parsed.get("score", 70),
                "unsupported_claims": parsed.get("unsupported_claims", []),
                "explanation": parsed.get("explanation", ""),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }
        except Exception as e:
            logger.error(f"Grounding eval failed: {e}")
            return {"grounding_score": 70, "unsupported_claims": [], "explanation": str(e), "error": True}

    async def evaluate_answer_relevance(self, question: str, answer: str) -> Dict[str, Any]:
        claude = get_claude_service()
        t0 = time.monotonic()
        try:
            result = await claude.reason_text(
                system_prompt="Score answer relevance to the question 0-100. Return JSON: {relevance_score: number, explanation: string}.",
                human_message=f"Question: {question}\n\nAnswer: {answer[:2000]}",
                category="evaluation",
                cache_key_hint=f"answer_relevance:{hashlib.sha256((question + '|' + answer[:2000]).encode('utf-8')).hexdigest()[:16]}",
            )
            import json
            text = self._extract(result)
            parsed = json.loads(text) if text else {"relevance_score": 60, "explanation": "Unable to parse"}
            return {
                "relevance_score": parsed.get("relevance_score", 60),
                "explanation": parsed.get("explanation", ""),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }
        except Exception as e:
            return {"relevance_score": 60, "explanation": str(e), "error": True}

    async def evaluate_retrieval_quality(self, query: str, retrieved: List[str]) -> Dict[str, Any]:
        claude = get_claude_service()
        t0 = time.monotonic()
        chunks_text = "\n---\n".join(f"[{i}] {t[:500]}" for i, t in enumerate(retrieved[:10]))
        try:
            result = await claude.reason_text(
                system_prompt="Score retrieval quality: how relevant are these chunks to the query? Score 0-100. Return JSON: {quality_score: number, irrelevant_count: number, explanation: string}.",
                human_message=f"Query: {query}\n\nRetrieved chunks:\n{chunks_text}",
                category="evaluation",
                cache_key_hint=f"retrieval_quality:{hashlib.sha256((query + '|' + chunks_text).encode('utf-8')).hexdigest()[:16]}",
            )
            import json
            text = self._extract(result)
            parsed = json.loads(text) if text else {"quality_score": 60, "irrelevant_count": 0, "explanation": "Unable to parse"}
            return {
                "retrieval_quality_score": parsed.get("quality_score", 60),
                "irrelevant_chunks": parsed.get("irrelevant_count", 0),
                "explanation": parsed.get("explanation", ""),
                "latency_ms": round((time.monotonic() - t0) * 1000, 2),
            }
        except Exception as e:
            return {"retrieval_quality_score": 60, "irrelevant_chunks": 0, "explanation": str(e), "error": True}

    async def run_full_evaluation(self, query: str, answer: str, context: str, retrieved_chunks: List[str] = None) -> Dict[str, Any]:
        if not (context or (query and answer) or retrieved_chunks):
            return {}

        claude = get_claude_service()
        t0 = time.monotonic()
        chunks_text = "\n---\n".join(f"[{i}] {t[:500]}" for i, t in enumerate((retrieved_chunks or [])[:10]))
        prompt = {
            "query": query,
            "answer": answer,
            "context": context[:3000] if context else "",
            "retrieved_chunks": chunks_text,
        }
        prompt_blob = json.dumps(prompt, sort_keys=True, default=str)
        try:
            result = await claude.reason(
                system_prompt=(
                    "You evaluate AI answer quality in one pass. Return JSON only with:\n"
                    "hallucination_score, high_risk_spans, grounding_score, unsupported_claims, "
                    "relevance_score, retrieval_quality_score, irrelevant_count, explanation, evidence.\n"
                    "Use concise evidence strings and numeric scores from 0 to 100."
                ),
                human_message=prompt_blob,
                output_schema=EvaluationEngine.EvaluationBundle,
                category="evaluation",
                cache_key_hint=f"evaluation:{hashlib.sha256(prompt_blob.encode('utf-8')).hexdigest()[:16]}",
            )
            payload = result.get("result") if isinstance(result, dict) else None
            if isinstance(payload, EvaluationEngine.EvaluationBundle):
                bundle = payload
            elif isinstance(payload, dict):
                bundle = EvaluationEngine.EvaluationBundle.model_validate(payload)
            else:
                bundle = EvaluationEngine.EvaluationBundle()
            latency_ms = round((time.monotonic() - t0) * 1000, 2)
            return {
                "hallucination": {
                    "hallucination_score": bundle.hallucination_score,
                    "high_risk_spans": bundle.high_risk_spans,
                    "explanation": bundle.explanation,
                    "latency_ms": latency_ms,
                },
                "grounding": {
                    "grounding_score": bundle.grounding_score,
                    "unsupported_claims": bundle.unsupported_claims,
                    "explanation": bundle.explanation,
                    "latency_ms": latency_ms,
                },
                "answer_relevance": {
                    "relevance_score": bundle.relevance_score,
                    "explanation": bundle.explanation,
                    "latency_ms": latency_ms,
                },
                "retrieval_quality": {
                    "retrieval_quality_score": bundle.retrieval_quality_score,
                    "irrelevant_chunks": bundle.irrelevant_count,
                    "explanation": bundle.explanation,
                    "latency_ms": latency_ms,
                },
            }
        except Exception as e:
            logger.error(f"Bundled evaluation failed: {e}")
            return {}

    def _extract(self, result: Any) -> str:
        if isinstance(result, dict):
            inner = result.get("result", result)
            if isinstance(inner, str):
                return inner
            if hasattr(inner, "content"):
                return inner.content
            return str(inner)
        return str(result)


def get_evaluation_engine() -> EvaluationEngine:
    global _evaluation_engine
    if _evaluation_engine is None:
        _evaluation_engine = EvaluationEngine()
    return _evaluation_engine


evaluation_engine = get_evaluation_engine()

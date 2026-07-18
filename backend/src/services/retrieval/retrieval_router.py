"""
Retrieval router for collection-aware query routing.

Determines target Qdrant collections based on query intent and content.
Supports federated retrieval across multiple collections when queries
span resume + job matching needs.

Stateless, async-safe, observable. Worker-safe.
"""
import logging
import re
from typing import List, Dict, Optional

from src.schemas.retrieval import RoutingDecision, QueryIntent
from src.observability.metrics import (
    RETRIEVAL_ROUTING_COUNT,
    RETRIEVAL_FEDERATED_COUNT,
    ROUTING_CONFIDENCE,
)

logger = logging.getLogger(__name__)

# Collection routing classification patterns
ROUTE_PATTERNS: Dict[str, List[str]] = {
    "careeros_resumes": [
        r"\bresume\b", r"\bcv\b", r"\bcandidate\b", r"\bcandidates?\b",
        r"\bapplicant\b", r"\bexperience\b", r"\bskills?\b",
        r"\byears?\s+of\b", r"\bled\b.*\bteam\b", r"\bmanaged\b",
        r"\bengineer\b", r"\bdeveloper\b", r"\barchitect\b",
        r"\bhas\s+experience\b", r"\bproficient\b", r"\bworked\s+at\b",
    ],
    "careeros_jobs": [
        r"\bjob\b", r"\brole\b", r"\bposition\b", r"\bopening\b",
        r"\bhiring\b", r"\brecruiting\b", r"\brequisition\b",
        r"\bjob\s+description\b", r"\breq\s+#?\d+\b",
        r"\brequirements?\b", r"\bqualifications?\b",
    ],
    "careeros_knowledge": [
        r"\bhow\s+to\b", r"\bwhat\s+is\b", r"\bexplain\b",
        r"\btutorial\b", r"\bguide\b", r"\bdocumentation\b",
        r"\bbest\s+practices?\b", r"\btips?\b",
    ],
}

# Default collection weights by route
DEFAULT_WEIGHTS: Dict[str, float] = {
    "careeros_resumes": 0.6,
    "careeros_jobs": 0.3,
    "careeros_knowledge": 0.1,
}


class RetrievalRouter:
    """Routes queries to the appropriate Qdrant collection(s)."""

    async def route(
        self,
        query: str,
        intent: Optional[QueryIntent] = None,
        user_context: Optional[Dict] = None,
    ) -> RoutingDecision:
        """Determine which collection(s) to query.

        Args:
            query: Natural language search query
            intent: Pre-classified query intent (optional)
            user_context: User session context for adaptive routing

        Returns:
            RoutingDecision with target collections, weights, and confidence
        """
        query_lower = query.lower()
        collection_scores: Dict[str, float] = {}
        match_details: Dict[str, List[str]] = {}

        for collection, patterns in ROUTE_PATTERNS.items():
            matches = [p for p in patterns if re.search(p, query_lower)]
            if matches:
                score = min(1.0, len(matches) / 3.0)
                collection_scores[collection] = score
                match_details[collection] = matches[:3]

        # If no patterns matched, default to resumes
        if not collection_scores:
            collection_scores["careeros_resumes"] = 0.5

        # Build weighted target list
        target_collections = sorted(
            collection_scores.keys(),
            key=lambda c: collection_scores[c],
            reverse=True,
        )

        is_federated = len(target_collections) > 1

        # Build collection weights
        total_score = sum(collection_scores.values()) or 1.0
        weights = {
            c: round(collection_scores[c] / total_score, 3)
            for c in target_collections
        }

        # Routing confidence
        confidence = max(collection_scores.values()) if collection_scores else 0.5

        # Federated retrieval count
        if is_federated:
            RETRIEVAL_FEDERATED_COUNT.inc()

        for coll in target_collections:
            RETRIEVAL_ROUTING_COUNT.labels(
                route="federated" if is_federated else "single",
                collection=coll,
            ).inc()

        ROUTING_CONFIDENCE.observe(confidence)

        # Build routing reason
        reasons = []
        for coll in list(target_collections)[:2]:
            if coll in match_details:
                reasons.append(
                    f"{coll}: matched {len(match_details[coll])} patterns"
                )
        reason = "; ".join(reasons) if reasons else "default route to resumes"

        return RoutingDecision(
            query=query,
            target_collections=target_collections,
            collection_weights=weights,
            routing_confidence=round(confidence, 3),
            routing_reason=reason,
            is_federated=is_federated,
        )

    async def route_single(self, query: str) -> str:
        """Route to a single most-likely collection."""
        decision = await self.route(query)
        return decision.target_collections[0] if decision.target_collections else "careeros_resumes"

    async def should_federate(self, query: str) -> bool:
        """Check if federated retrieval is needed."""
        decision = await self.route(query)
        return decision.is_federated


# Module-level singleton
_retrieval_router: Optional[RetrievalRouter] = None


def get_retrieval_router() -> RetrievalRouter:
    global _retrieval_router
    if _retrieval_router is None:
        _retrieval_router = RetrievalRouter()
    return _retrieval_router


def reset_retrieval_router() -> None:
    global _retrieval_router
    _retrieval_router = None


def __getattr__(name: str):
    if name == "retrieval_router":
        return get_retrieval_router()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

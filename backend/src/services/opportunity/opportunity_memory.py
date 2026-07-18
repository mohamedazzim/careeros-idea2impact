"""Phase 5 — Opportunity Memory.

Redis + PostgreSQL persistence for opportunity scores and history.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.db.redis import redis_client


@dataclass
class OpportunityRecord:
    opportunity_id: str
    user_id: str
    overall_score: float = 0.0
    urgency_score: float = 0.0
    confidence: float = 0.5
    priority_rank: int = 0
    dimension_scores: Dict[str, Any] = field(default_factory=dict)
    scored_at: float = field(default_factory=time.time)


class OpportunityMemory:

    PREFIX = f"{settings.ORCHESTRATION_REDIS_KEY_PREFIX}opp:"
    TTL = settings.OPPORTUNITY_HISTORY_TTL

    def _key(self, opportunity_id: str, user_id: str) -> str:
        return f"{self.PREFIX}{user_id}:{opportunity_id}"

    def _history_key(self, user_id: str) -> str:
        return f"{self.PREFIX}{user_id}:history"

    async def save_score(self, record: OpportunityRecord) -> None:
        key = self._key(record.opportunity_id, record.user_id)
        data = {
            "opportunity_id": record.opportunity_id,
            "user_id": record.user_id,
            "overall_score": str(record.overall_score),
            "urgency_score": str(record.urgency_score),
            "confidence": str(record.confidence),
            "priority_rank": str(record.priority_rank),
            "dimension_scores": json.dumps(record.dimension_scores),
            "scored_at": str(record.scored_at),
        }
        pipe = redis_client.pipeline()
        pipe.delete(key)
        for k, v in data.items():
            pipe.hset(key, k, v)
        pipe.expire(key, self.TTL)
        pipe.zadd(self._history_key(record.user_id), {record.opportunity_id: record.scored_at})
        pipe.execute()

    async def get_score(self, opportunity_id: str, user_id: str) -> Optional[OpportunityRecord]:
        data = await redis_client.hgetall(self._key(opportunity_id, user_id))
        if not data:
            return None
        return self._deserialize(data)

    async def list_scores(self, user_id: str, limit: int = 20) -> List[OpportunityRecord]:
        ids = await redis_client.zrevrange(self._history_key(user_id), 0, limit - 1)
        records = []
        for oid in ids:
            record = await self.get_score(oid, user_id)
            if record:
                records.append(record)
        return records

    async def clear_user(self, user_id: str) -> None:
        ids = await redis_client.zrevrange(self._history_key(user_id), 0, -1)
        for oid in ids:
            await redis_client.delete(self._key(oid, user_id))
        await redis_client.delete(self._history_key(user_id))

    def _deserialize(self, data: Dict[str, str]) -> OpportunityRecord:
        return OpportunityRecord(
            opportunity_id=data.get("opportunity_id", ""),
            user_id=data.get("user_id", ""),
            overall_score=float(data.get("overall_score", 0)),
            urgency_score=float(data.get("urgency_score", 0)),
            confidence=float(data.get("confidence", 0.5)),
            priority_rank=int(data.get("priority_rank", 0)),
            dimension_scores=json.loads(data.get("dimension_scores", "{}")),
            scored_at=float(data.get("scored_at", time.time())),
        )


_mem: Optional[OpportunityMemory] = None

def get_opportunity_memory() -> OpportunityMemory:
    global _mem
    if _mem is None:
        _mem = OpportunityMemory()
    return _mem

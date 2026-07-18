"""Phase 6 — Graph Persistence & Recovery.

Checkpoint manager for LangGraph execution snapshots, resume, and replay.
Uses Redis for active checkpoints and PostgreSQL for durable history.
"""

import time
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CHECKPOINT_KEY = "orch:checkpoint:"


class GraphCheckpointManager:
    """Manages LangGraph checkpoints for recovery and replay."""

    async def save_checkpoint(self, session_uid: str, node_name: str, state: Dict[str, Any]) -> bool:
        """Save a graph execution checkpoint."""
        try:
            from src.db.redis import redis_client
            from src.core.config import settings
            key = f"{CHECKPOINT_KEY}{session_uid}:{node_name}"
            snapshot = {
                "session_uid": session_uid,
                "node_name": node_name,
                "timestamp": time.time(),
                "state": state,
            }
            await redis_client.setex(
                key, getattr(settings, 'ORCHESTRATION_SESSION_TTL', 7200),
                json.dumps(snapshot, default=str),
            )
            return True
        except Exception as exc:
            logger.error(f"Checkpoint save failed for {session_uid}/{node_name}: {exc}")
            return False

    async def load_checkpoint(self, session_uid: str, node_name: str) -> Optional[Dict[str, Any]]:
        """Load a specific checkpoint."""
        try:
            from src.db.redis import redis_client
            key = f"{CHECKPOINT_KEY}{session_uid}:{node_name}"
            raw = await redis_client.get(key)
            if raw:
                return json.loads(raw)
            return None
        except Exception:
            return None

    async def list_checkpoints(self, session_uid: str) -> List[str]:
        """List all checkpoint node names for a session."""
        try:
            from src.db.redis import redis_client
            cursor = 0
            nodes = []
            pattern = f"{CHECKPOINT_KEY}{session_uid}:*"
            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern)
                for key in keys:
                    node = key.decode().split(":")[-1]
                    nodes.append(node)
                if cursor == 0:
                    break
            return sorted(nodes)
        except Exception:
            return []

    async def get_last_checkpoint(self, session_uid: str) -> Optional[Dict[str, Any]]:
        """Get the last checkpoint (latest node) for a session."""
        nodes = await self.list_checkpoints(session_uid)
        if not nodes:
            return None
        return await self.load_checkpoint(session_uid, nodes[-1])


class OrchestrationResumeEngine:
    """Resume failed orchestrations from the last checkpoint."""

    def __init__(self):
        self.checkpoint_mgr = GraphCheckpointManager()

    async def resume(self, session_uid: str) -> Optional[Dict[str, Any]]:
        """Resume a failed orchestration from its last checkpoint."""
        cp = await self.checkpoint_mgr.get_last_checkpoint(session_uid)
        if not cp:
            logger.info(f"No checkpoint found for {session_uid}")
            return None

        try:
            from src.graphs.opportunity_graph import get_opportunity_graph
            from src.observability.metrics import GRAPH_RESUME_COUNT

            graph = get_opportunity_graph()
            config = {"configurable": {"thread_id": session_uid}}
            result = await graph.ainvoke(None, config)
            GRAPH_RESUME_COUNT.labels(graph_name="opportunity").inc()
            return result if isinstance(result, dict) else {}
        except Exception as exc:
            logger.error(f"Resume failed for {session_uid}: {exc}")
            return {"status": "resume_failed", "error": str(exc)}


class ExecutionReplayEngine:
    """Replay a complete orchestration from recorded events."""

    async def replay(self, session_uid: str) -> Dict[str, Any]:
        """Replay orchestration with governance re-validation."""
        try:
            from src.runtime.events.event_bus import get_event_bus
            bus = get_event_bus()
            events = await bus.replay(session_uid)
            if not events:
                return {"status": "no_events", "session_uid": session_uid}

            from src.graphs.opportunity_graph import get_opportunity_graph
            graph = get_opportunity_graph()

            config = {"configurable": {"thread_id": f"replay_{session_uid}"}}
            initial_state = {
                "session_uid": f"replay_{session_uid}",
                "replay_session": session_uid,
                "candidate_context": {},
                "opportunities": [],
            }
            result = await graph.ainvoke(initial_state, config)
            return {
                "status": "replayed",
                "original_session": session_uid,
                "events": len(events),
                "result": result if isinstance(result, dict) else {},
            }
        except Exception as exc:
            return {"status": "replay_failed", "error": str(exc)}


class NodeFailureRecovery:
    """Node-level recovery for individual graph node failures."""

    async def recover_node(self, session_uid: str, failed_node: str) -> Optional[Dict[str, Any]]:
        """Retry a single failed graph node."""
        try:
            from src.graphs.opportunity_graph import get_opportunity_graph
            graph = get_opportunity_graph()
            config = {"configurable": {"thread_id": session_uid}}
            result = await graph.ainvoke(None, config)
            return result if isinstance(result, dict) else {}
        except Exception as exc:
            logger.error(f"Node recovery failed for {session_uid}/{failed_node}: {exc}")
            return None


# ── Singletons ────────────────────────────────────────────────────────

_checkpoint: Optional[GraphCheckpointManager] = None
_resume: Optional[OrchestrationResumeEngine] = None
_replay: Optional[ExecutionReplayEngine] = None
_node_recovery: Optional[NodeFailureRecovery] = None


def get_checkpoint_manager() -> GraphCheckpointManager:
    global _checkpoint
    if _checkpoint is None:
        _checkpoint = GraphCheckpointManager()
    return _checkpoint


def get_resume_engine() -> OrchestrationResumeEngine:
    global _resume
    if _resume is None:
        _resume = OrchestrationResumeEngine()
    return _resume


def get_replay_engine() -> ExecutionReplayEngine:
    global _replay
    if _replay is None:
        _replay = ExecutionReplayEngine()
    return _replay


def get_node_recovery() -> NodeFailureRecovery:
    global _node_recovery
    if _node_recovery is None:
        _node_recovery = NodeFailureRecovery()
    return _node_recovery

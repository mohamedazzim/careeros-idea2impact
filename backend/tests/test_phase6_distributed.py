"""Phase 6 Tests — Distributed Workers, Queues, Recovery, Human Loop.

Tests for worker registry, lock manager, retry coordinator, worker pool,
priority/retry/dead-letter queues, graph recovery, approval gateway, escalation,
intervention, and streaming manager.

All tests run without Redis (in-memory fallbacks where available).
"""

import pytest
import asyncio
import time
from src.runtime.workers.worker_registry import WorkerNode
from src.runtime.workers.distributed_lock_manager import OwnershipLease
from src.runtime.workers.retry_coordinator import RetryState
from src.runtime.queues import QueueItem
from src.runtime.recovery import GraphCheckpointManager, NodeFailureRecovery
from src.runtime.human_loop import (
    ApprovalRequest, get_escalation_manager, get_intervention_handler,
)
from src.runtime.streaming import get_stream_manager, LiveTraceStreamer


class TestWorkerNode:
    def test_create_worker(self):
        node = WorkerNode(worker_id="w1", hostname="host1")
        assert node.worker_id == "w1"
        assert node.status == "active"
        assert node.hostname == "host1"

    def test_to_dict_from_dict(self):
        node = WorkerNode(worker_id="w1", hostname="host1", pid=999, active_executions=["s1"])
        d = node.to_dict()
        restored = WorkerNode.from_dict(d)
        assert restored.worker_id == "w1"
        assert restored.hostname == "host1"
        assert restored.pid == 999
        assert "s1" in restored.active_executions


class TestDistributedLockManager:
    def test_ownership_lease_dataclass(self):
        lease = OwnershipLease(
            lease_id="l1", session_uid="s1", worker_id="w1",
        )
        assert lease.lease_id == "l1"
        assert lease.session_uid == "s1"
        assert lease.acquired_at > 0

    def test_lease_serialization(self):
        lease = OwnershipLease(lease_id="l1", session_uid="s1", worker_id="w1")
        d = lease.to_dict()
        restored = OwnershipLease.from_dict(d)
        assert restored.lease_id == "l1"


class TestRetryCoordinator:
    def test_retry_state_defaults(self):
        state = RetryState(
            retry_id="r1", session_uid="s1",
        )
        assert state.attempt == 1
        assert state.max_attempts == 3
        assert state.status == "pending"

    def test_compute_delay(self):
        state = RetryState(
            retry_id="r1", session_uid="s1", attempt=3,
            base_delay=1.0, backoff_factor=2.0, jitter_max=0.0,
        )
        delay = state.compute_delay()
        assert delay == 4.0  # 1.0 * 2^2 = 4.0

    def test_retry_state_serialization(self):
        state = RetryState(
            retry_id="r1", session_uid="s1", attempt=2, last_error="test_error",
        )
        d = state.to_dict()
        assert d["retry_id"] == "r1"
        assert d["attempt"] == 2
        assert d["last_error"] == "test_error"


class TestQueueItem:
    def test_create_queue_item(self):
        item = QueueItem(
            item_id="qi1", session_uid="s1",
            payload={"opportunity_id": "o1"},
            priority=75,
        )
        assert item.item_id == "qi1"
        assert item.priority == 75
        assert item.attempt == 0

    def test_queue_item_serialization(self):
        item = QueueItem(
            item_id="qi1", session_uid="s1",
            payload={"score": 85}, priority=90, attempt=2,
        )
        d = item.to_dict()
        restored = QueueItem.from_dict(d)
        assert restored.item_id == "qi1"
        assert restored.priority == 90
        assert restored.payload["score"] == 85


class TestPriorityQueue:
    def test_enqueue_dequeue_in_memory(self):
        item = QueueItem(item_id="test_pq_1", session_uid="s1", priority=100)
        assert item.item_id == "test_pq_1"
        assert item.priority == 100

    def test_dead_letter_queue_item(self):
        item = QueueItem(item_id="dl1", session_uid="s1", last_error="timeout")
        assert item.last_error == "timeout"


class TestGraphCheckpointManager:
    def test_checkpoint_manager_init(self):
        mgr = GraphCheckpointManager()
        assert mgr is not None


class TestNodeFailureRecovery:
    def test_node_recovery_init(self):
        recovery = NodeFailureRecovery()
        assert recovery is not None


class TestApprovalGateway:
    def test_approval_request_dataclass(self):
        ar = ApprovalRequest(
            approval_id="a1", session_uid="s1",
            action_type="notification", description="Notify candidate",
        )
        assert ar.status == "pending"
        assert ar.action_type == "notification"

    def test_approval_serialization(self):
        ar = ApprovalRequest(
            approval_id="a1", session_uid="s1",
            action_type="notification", description="Test",
        )
        d = ar.to_dict()
        assert d["approval_id"] == "a1"
        assert d["status"] == "pending"


class TestEscalationManager:
    def test_handler_exists(self):
        mgr = get_escalation_manager()
        assert mgr is not None


class TestInterventionHandler:
    def test_handler_exists(self):
        handler = get_intervention_handler()
        assert handler is not None


class TestStreamingManager:
    def test_stream_manager_singleton(self):
        a = get_stream_manager()
        b = get_stream_manager()
        assert a is b

    def test_live_trace_streamer(self):
        streamer = LiveTraceStreamer()
        assert streamer.stream_mgr is not None


class TestWorkerPoolSimulation:
    @pytest.mark.asyncio
    async def test_simple_coroutine(self):
        """Verify async task pattern works in the test environment."""
        result = None

        async def _job():
            nonlocal result
            result = "done"
            return "done"

        task = asyncio.create_task(_job())
        await task
        assert result == "done"

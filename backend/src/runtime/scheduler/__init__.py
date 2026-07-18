"""Phase 6 — Autonomous Scheduler.

Periodic job scheduler for autonomous opportunity scanning and orchestration
wakeups using Redis for distributed scheduling safety.
"""

import uuid
import time
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional
from src.core.config import settings

logger = logging.getLogger(__name__)

SCHEDULER_LOCK_KEY = "orch:scheduler:lock"
SCHEDULER_RUN_KEY = "orch:scheduler:last_run"


@dataclass
class ScheduledJob:
    job_id: str
    name: str
    interval_seconds: int
    fn: Optional[Callable[[], Coroutine[Any, Any, Any]]] = None
    last_run: float = 0.0
    next_run: float = 0.0
    status: str = "pending"
    errors: List[str] = field(default_factory=list)


class AutonomousScheduler:
    """Distributed scheduler for recurring orchestration jobs."""

    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def register_job(self, name: str, interval_seconds: int,
                           fn: Callable[[], Coroutine[Any, Any, Any]]) -> str:
        job_id = str(uuid.uuid4())
        now = time.time()
        self._jobs[job_id] = ScheduledJob(
            job_id=job_id,
            name=name,
            interval_seconds=interval_seconds,
            fn=fn,
            next_run=now + interval_seconds,
        )
        logger.info(f"Scheduled job '{name}' every {interval_seconds}s (id={job_id})")
        return job_id

    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Autonomous scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Autonomous scheduler stopped")

    async def _loop(self):
        while self._running:
            try:
                acquired = await self._acquire_scheduler_lock()
                if not acquired:
                    await asyncio.sleep(10)
                    continue

                now = time.time()
                for job in self._jobs.values():
                    if now >= job.next_run and job.status == "pending":
                        await self._run_job(job)

                await self._release_scheduler_lock()
            except Exception as exc:
                logger.error(f"Scheduler loop error: {exc}")
            await asyncio.sleep(5)

    async def _run_job(self, job: ScheduledJob):
        """Execute a single scheduled job."""
        job.status = "running"
        job.last_run = time.time()
        try:
            if job.fn:
                await job.fn()
            job.status = "completed"
            job.next_run = time.time() + job.interval_seconds
            await self._record_last_run(job.name)
            logger.info(f"Job '{job.name}' completed, next run in {job.interval_seconds}s")
        except Exception as exc:
            job.status = "failed"
            job.errors.append(str(exc))
            job.next_run = time.time() + min(job.interval_seconds, 60)
            logger.error(f"Job '{job.name}' failed: {exc}")

    async def _acquire_scheduler_lock(self) -> bool:
        try:
            from src.db.redis import redis_client
            return await redis_client.set(SCHEDULER_LOCK_KEY, "1", nx=True, ex=30)
        except Exception:
            return True

    async def _release_scheduler_lock(self):
        try:
            from src.db.redis import redis_client
            await redis_client.delete(SCHEDULER_LOCK_KEY)
        except Exception:
            pass

    async def _record_last_run(self, job_name: str):
        try:
            from src.db.redis import redis_client
            await redis_client.hset(SCHEDULER_RUN_KEY, job_name, str(time.time()))
        except Exception:
            pass

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        return {
            "job_id": job.job_id,
            "name": job.name,
            "interval_seconds": job.interval_seconds,
            "last_run": job.last_run,
            "next_run": job.next_run,
            "status": job.status,
            "errors": job.errors[-5:],
        }

    async def list_jobs(self) -> List[Dict[str, Any]]:
        return [await self.get_job_status(jid) for jid in self._jobs]


class OpportunityScanScheduler:
    """Schedules periodic opportunity scans for all users."""

    async def scan_opportunities(self):
        """Scan and score new opportunities from job boards."""
        try:
            from src.agents.opportunity_discovery_agent import get_opportunity_discovery_agent
            agent = get_opportunity_discovery_agent()
            result = await agent.discover(user_id="system")
            logger.info(f"Opportunity scan: {result.status}, {len(result.discovered_opportunities)} found")
        except Exception as exc:
            logger.error(f"Opportunity scan failed: {exc}")


_scheduler: Optional[AutonomousScheduler] = None
_scan_scheduler: Optional[OpportunityScanScheduler] = None


def get_scheduler() -> AutonomousScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutonomousScheduler()
    return _scheduler


def get_scan_scheduler() -> OpportunityScanScheduler:
    global _scan_scheduler
    if _scan_scheduler is None:
        _scan_scheduler = OpportunityScanScheduler()
    return _scan_scheduler

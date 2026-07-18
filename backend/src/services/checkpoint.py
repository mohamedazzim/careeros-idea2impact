"""Persistent LangGraph checkpoint saver.

Priority chain:
  1. SqliteSaver — file-based persistence across restarts (langgraph.checkpoint.sqlite)
  2. MemorySaver — in-memory only (graceful fallback)

Checkpoints survive process restart with SqliteSaver.
"""

import logging
import os
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

_persistent_saver = None


def _try_sqlite_saver():
    """Try AsyncSqliteSaver with configured db path. Return None if unavailable."""
    try:
        from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver
        from src.core.config import settings

        db_path = getattr(settings, "CHECKPOINT_DB_PATH", "./data/langgraph_checkpoints.db")
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        saver = AsyncSqliteSaver.from_conn_string(db_path)
        logger.info("Using AsyncSqliteSaver — checkpoints persist across restarts at %s", db_path)
        return saver
    except Exception as exc:
        logger.debug("AsyncSqliteSaver unavailable: %s", exc)
        return None


def get_checkpoint_saver():
    """Lazy-init singleton checkpoint saver.

    Priority chain:
      1. AsyncSqliteSaver — file-based persistence across restarts (langgraph.checkpoint.aiosqlite)
      2. PostgresCheckpointSaver — PostgreSQL persistence (requires langgraph_checkpoints table)
      3. MemorySaver — in-memory only (graceful fallback, checkpoints lost on restart)
    """
    global _persistent_saver
    if _persistent_saver is not None:
        return _persistent_saver

    # Priority 1: AsyncSqliteSaver (most reliable file-based persistence)
    saver = _try_sqlite_saver()
    if saver is not None:
        _persistent_saver = saver
        return _persistent_saver

    # Priority 2: PostgreSQL checkpoint saver (requires DB table)
    try:
        from src.services.postgres_checkpoint import PostgresCheckpointSaver
        _persistent_saver = PostgresCheckpointSaver()
        logger.info("Using PostgreSQL LangGraph checkpoint saver")
        return _persistent_saver
    except Exception as exc:
        logger.warning("PostgreSQL checkpoint saver unavailable: %s", exc)

    # Priority 3: MemorySaver — no persistence across restarts
    logger.warning(
        "No persistent checkpoint saver available — using MemorySaver (checkpoints lost on restart). "
        "Install aiosqlite for persistent checkpointing or create the langgraph_checkpoints table."
    )
    _persistent_saver = MemorySaver()
    return _persistent_saver


def reset_checkpoint_saver():
    """Reset singleton for testing."""
    global _persistent_saver
    _persistent_saver = None

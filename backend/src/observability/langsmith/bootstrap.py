"""Install LangSmith guardrails early during app startup."""
from __future__ import annotations

import logging
from typing import Optional

import langsmith as external_langsmith

from .breaker import install_langsmith_log_filter

logger = logging.getLogger(__name__)

_installed = False


def install_langsmith_guard() -> None:
    """Patch LangSmith entry points so later imports use the guarded wrapper."""
    global _installed
    if _installed:
        return

    install_langsmith_log_filter()

    try:
        from .decorators import traceable, get_current_run_id, current_run_id

        external_langsmith.traceable = traceable  # type: ignore[attr-defined]
        external_langsmith.get_current_run_id = get_current_run_id  # type: ignore[attr-defined]
        external_langsmith.current_run_id = current_run_id  # type: ignore[attr-defined]
        logger.info("LangSmith guard installed")
    except Exception as exc:
        logger.warning("LangSmith guard bootstrap skipped: %s", str(exc)[:200])

    _installed = True

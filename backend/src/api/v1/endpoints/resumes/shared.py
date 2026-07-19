"""
Shared utilities for resume endpoints.
Phase 17.7 — Re-exports canonical auth deps from src.api.deps.

Resume endpoints use current_user: str, so get_current_user here aliases get_current_user_id.
Other endpoints should use the full get_current_user from src.api.deps for dict output.
"""
import logging

from src.api.deps import get_current_user_id

logger = logging.getLogger(__name__)

# Resume endpoints historically expect str user_id from get_current_user
get_current_user = get_current_user_id

__all__ = ["get_current_user", "get_current_user_id"]

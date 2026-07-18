"""
LangSmith feedback operations.
Submit and manage feedback for runs.
"""
import logging
from typing import Optional

from .client import get_manager
from .decorators import get_current_run_id

logger = logging.getLogger(__name__)


def submit_feedback(
    run_id: Optional[str] = None,
    key: str = "user_feedback",
    score: Optional[float] = None,
    comment: Optional[str] = None
) -> Optional[str]:
    """
    Submit feedback for a run.
    
    Args:
        run_id: Run ID (defaults to current run from context)
        key: Feedback key/category
        score: Numerical score (e.g., 0-1 or 1-5)
        comment: Text comment
        
    Returns:
        Feedback ID if successful
    """
    manager = get_manager()
    
    if not manager.enabled:
        logger.debug("LangSmith not enabled, skipping feedback")
        return None
    
    run_id = run_id or get_current_run_id()
    if not run_id:
        logger.warning("No run_id provided or found in context")
        return None
    
    try:
        feedback = manager.client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            comment=comment
        )
        logger.info(f"Feedback submitted for run {run_id}: {key}={score}")
        return feedback.id
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        return None

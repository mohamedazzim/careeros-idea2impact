import logging
import time
from typing import Optional, Union
from src.schemas.security import AuditLog

logger = logging.getLogger("audit_logger")

class AuditLogger:
    def log_event(
        self,
        action: str,
        resource: str,
        result: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Union[dict, str, None] = None
    ) -> AuditLog:
        """
        Create and record an immutable audit log.
        """
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource=resource,
            timestamp=time.time(),
            ip_address=ip_address,
            user_agent=user_agent,
            result=result,
            details=details
        )
        
        # Log to structured standard out (consumed by LangSmith/Datadog in production)
        logger.info(f"AUDIT_EVENT: {audit_entry.model_dump_json()}")
        
        return audit_entry

audit_logger = AuditLogger()

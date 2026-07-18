import contextvars
from typing import Optional

request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
user_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("user_id", default=None)
workflow_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("workflow_id", default=None)

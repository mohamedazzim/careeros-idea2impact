"""RC3.1 Pipedream webhook adapter with retry and dead-letter support."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx

from src.core.config import settings

RETRY_DELAYS = [60, 300, 900]  # 1 min, 5 min, 15 min


class PipedreamAdapter:
    async def send(self, payload: Dict[str, Any]) -> tuple[str, Dict[str, Any] | None]:
        webhook_url = (settings.PIPEDREAM_WEBHOOK_URL or "").strip()
        if not webhook_url:
            return "skipped_not_configured", {"reason": "PIPEDREAM_WEBHOOK_URL_missing"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(webhook_url, json=payload)
            return (
                "delivered" if 200 <= response.status_code < 300 else "failed",
                {
                    "status_code": response.status_code,
                    "body_preview": response.text[:500],
                    "body": self._response_body(response),
                },
            )
        except Exception as exc:
            return "failed", {"error": str(exc)}

    @staticmethod
    def _response_body(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text[:500]

    async def send_with_retry(
        self,
        payload: Dict[str, Any],
        *,
        correlation_id: str = "",
    ) -> tuple[str, Dict[str, Any] | None]:
        webhook_url = (settings.PIPEDREAM_WEBHOOK_URL or "").strip()
        if not webhook_url:
            return "skipped_not_configured", {"reason": "PIPEDREAM_WEBHOOK_URL_missing"}

        last_error: Optional[Dict[str, Any]] = None
        for attempt in range(len(RETRY_DELAYS) + 1):
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    response = await client.post(webhook_url, json=payload)
                if 200 <= response.status_code < 300:
                    return "delivered", {
                        "status_code": response.status_code,
                        "body_preview": response.text[:500],
                        "attempt": attempt + 1,
                        "correlation_id": correlation_id,
                    }
                last_error = {
                    "status_code": response.status_code,
                    "body_preview": response.text[:500],
                    "attempt": attempt + 1,
                }
            except Exception as exc:
                last_error = {"error": str(exc), "attempt": attempt + 1}

            if attempt < len(RETRY_DELAYS):
                await asyncio.sleep(RETRY_DELAYS[attempt])

        return "dead_letter", {**(last_error or {}), "dead_letter": True, "reason": "max_retries_exceeded"}


def get_pipedream_adapter() -> PipedreamAdapter:
    return PipedreamAdapter()

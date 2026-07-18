"""Gemini LLM provider — supports gemini-2.5-flash and gemini-2.5-pro."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx


from .provider import LLMProvider, Message

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(LLMProvider):
    """Google Gemini provider via REST API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        timeout_s: float = 60.0,
        max_retries: int = 3,
        retry_base_delay: float = 2.0,
    ):
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def _convert_messages(
        self, messages: List[Message]
    ) -> tuple[str, list[dict]]:
        """Convert OpenAI-style messages to Gemini format."""
        system_instruction = ""
        contents = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = content
            else:
                contents.append({"role": "model" if role == "assistant" else "user", "parts": [{"text": content}]})

        return system_instruction, contents

    async def chat(
        self,
        messages: List[Message],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stream: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
        cache_key_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        system_instruction, contents = self._convert_messages(messages)

        generation_config: dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        if response_format and response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{GEMINI_BASE_URL}/models/{self._model}:generateContent?key={self._api_key}"

        last_error = None
        for attempt in range(self._max_retries):
            t0 = time.time()
            try:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    resp = await client.post(url, json=payload)
                    latency_ms = round((time.time() - t0) * 1000, 1)

                    if resp.status_code == 429:
                        wait = self._retry_base_delay * (2 ** attempt)
                        logger.warning("Gemini 429 — retrying in %.1fs (attempt %d)", wait, attempt + 1)
                        await asyncio.sleep(wait)
                        continue

                    if resp.status_code >= 500:
                        wait = self._retry_base_delay * (2 ** attempt)
                        logger.warning("Gemini %d — retrying in %.1fs (attempt %d)", resp.status_code, wait, attempt + 1)
                        await asyncio.sleep(wait)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    candidates = data.get("candidates", [])
                    text = ""
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)

                    usage = data.get("usageMetadata", {})

                    return {
                        "result": text,
                        "provider": self.provider_name,
                        "model": self._model,
                        "latency_ms": latency_ms,
                        "prompt_tokens": usage.get("promptTokenCount", 0),
                        "completion_tokens": usage.get("candidatesTokenCount", 0),
                        "total_tokens": usage.get("totalTokenCount", 0),
                        "status": "success",
                    }

            except httpx.TimeoutException:
                last_error = "timeout"
                wait = self._retry_base_delay * (2 ** attempt)
                logger.warning("Gemini timeout — retrying in %.1fs (attempt %d)", wait, attempt + 1)
                await asyncio.sleep(wait)
            except httpx.HTTPStatusError as exc:
                last_error = str(exc)
                if exc.response.status_code in (400, 403):
                    break
                wait = self._retry_base_delay * (2 ** attempt)
                logger.warning("Gemini HTTP %d — retrying in %.1fs", exc.response.status_code, wait)
                await asyncio.sleep(wait)
            except Exception as exc:
                last_error = str(exc)
                wait = self._retry_base_delay * (2 ** attempt)
                logger.warning("Gemini error: %s — retrying in %.1fs", exc, wait)
                await asyncio.sleep(wait)

        raise RuntimeError(f"Gemini provider failed after {self._max_retries} attempts: {last_error}")

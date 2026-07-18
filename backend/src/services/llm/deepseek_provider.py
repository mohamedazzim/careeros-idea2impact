"""DeepSeek provider via NVIDIA NIM OpenAI-compatible endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional

import httpx

from src.core.config import settings
from src.db.redis import get_redis
from .provider import LLMProvider, Message

logger = logging.getLogger(__name__)

LLM_CACHE_PREFIX = "careeros:llm:"
LLM_COOLDOWN_PREFIX = "careeros:llm:cooldown:"
LLM_INFLIGHT_PREFIX = "careeros:llm:inflight:"
LLM_CACHE_TTL = 3600
LLM_COOLDOWN_SECONDS = 60
LLM_MAX_CONCURRENT_REQUESTS = 1

_inflight_lock = asyncio.Lock()
_inflight_requests: Dict[str, asyncio.Future] = {}


class DeepSeekProvider(LLMProvider):
    """OpenAI-compatible DeepSeek provider hosted on NVIDIA NIM."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        self._api_key = api_key or settings.NVIDIA_API_KEY or ""
        self._base_url = (base_url or settings.NVIDIA_NIM_BASE_URL).rstrip("/")
        self._model = model or settings.DEEPSEEK_MODEL
        self._timeout_s = float(timeout_s or settings.CLAUDE_TIMEOUT)
        self._max_retries = int(max_retries if max_retries is not None else settings.CLAUDE_MAX_RETRIES)
        self._cache_ttl_s = int(getattr(settings, "LLM_CACHE_TTL_SECONDS", LLM_CACHE_TTL))
        self._cooldown_s = int(getattr(settings, "LLM_CACHE_COOLDOWN_SECONDS", LLM_COOLDOWN_SECONDS))
        self._request_semaphore = asyncio.Semaphore(
            max(1, int(getattr(settings, "LLM_MAX_CONCURRENT_REQUESTS", LLM_MAX_CONCURRENT_REQUESTS)))
        )

        if not self._api_key:
            logger.warning("NVIDIA_API_KEY is not configured; DeepSeek provider will fail until set")
        else:
            logger.info(
                "DeepSeekProvider initialized",
                extra={
                    "provider": self.provider_name,
                    "model": self._model,
                    "base_url": self._base_url,
                },
            )

    @property
    def provider_name(self) -> str:
        return "deepseek_nim"

    @property
    def model_name(self) -> str:
        return self._model

    async def chat(
        self,
        messages: List[Message],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stream: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
        cache_key_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format
        if stream:
            payload["stream"] = True

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        cache_key = None
        if not stream:
            cache_key = self._cache_key(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
                cache_key_hint=cache_key_hint,
            )
            cached = await self._get_cached_response(cache_key)
            if cached is not None:
                cached["cached"] = True
                cached.setdefault("provider", self.provider_name)
                cached.setdefault("model", self._model)
                logger.info(
                    "DeepSeek cache hit",
                    extra={
                        "provider": self.provider_name,
                        "model": self._model,
                        "cache_key": cache_key,
                        "request_id": cached.get("request_id"),
                        "response_id": cached.get("response_id"),
                    },
                )
                return cached

            cooldown_remaining = await self._cooldown_remaining()
            if cooldown_remaining > 0:
                raise RuntimeError(
                    f"DeepSeek NIM cooldown active for {cooldown_remaining:.0f}s; "
                    "cached response unavailable"
                )

            inflight_future, created = await self._acquire_inflight(cache_key)
            if not created:
                return await inflight_future

        start = time.monotonic()
        last_error: Optional[str] = None
        attempts_made = 0
        try:
            async with self._request_semaphore:
                for attempt in range(self._max_retries + 1):
                    attempts_made = attempt + 1
                    request_id = f"nim_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
                    try:
                        timeout = httpx.Timeout(self._timeout_s)
                        async with httpx.AsyncClient(base_url=self._base_url, timeout=timeout) as client:
                            if stream:
                                text, chunks, meta = await self._chat_stream(client, headers, payload)
                                elapsed_ms = round((time.monotonic() - start) * 1000, 2)
                                result = {
                                    "result": text,
                                    "content": text,
                                    "chunks": chunks,
                                    "streamed": True,
                                    "provider": self.provider_name,
                                    "model": self._model,
                                    "latency_ms": elapsed_ms,
                                    "cost": 0.0,
                                    "tokens": meta.get("tokens", {"input": 0, "output": 0}),
                                    "request_id": meta.get("request_id", request_id),
                                    "response_id": meta.get("response_id"),
                                    "domain": "general",
                                }
                                self._log_success(result)
                                return result

                            response = await client.post("/chat/completions", headers=headers, json=payload)
                            response.raise_for_status()
                            data = response.json()
                            result = self._normalize_response(data, start, request_id, response.headers)
                            if cache_key:
                                await self._set_cached_response(cache_key, result)
                                await self._succeed_inflight(cache_key, result)
                            self._log_success(result)
                            return result
                    except (httpx.TimeoutException, httpx.ConnectError) as exc:
                        last_error = str(exc)
                        logger.warning(
                            "DeepSeek request failed (attempt %s/%s): %s",
                            attempt + 1,
                            self._max_retries + 1,
                            exc,
                        )
                    except httpx.HTTPStatusError as exc:
                        last_error = f"{exc.response.status_code}: {exc.response.text[:500]}"
                        logger.warning(
                            "DeepSeek HTTP error (attempt %s/%s): %s",
                            attempt + 1,
                            self._max_retries + 1,
                            last_error,
                        )
                        if exc.response.status_code == 429:
                            await self._set_cooldown(exc.response.headers.get("retry-after"))
                            break
                        if exc.response.status_code not in {500, 502, 503, 504}:
                            break
                        retry_after = exc.response.headers.get("retry-after")
                        try:
                            retry_after_s = float(retry_after) if retry_after else 0.0
                        except ValueError:
                            retry_after_s = 0.0
                        backoff = max(retry_after_s, 5.0 * (attempt + 1), 2.0 ** attempt * 2.0)
                        await asyncio.sleep(min(backoff, 30.0))
                    except Exception as exc:
                        last_error = str(exc)
                        logger.exception("DeepSeek provider error")

                    if attempt < self._max_retries:
                        await asyncio.sleep(min(0.5 * (2 ** attempt), 2.0))

            elapsed_ms = round((time.monotonic() - start) * 1000, 2)
            raise RuntimeError(
                f"DeepSeek NIM chat failed after {attempts_made} attempts ({elapsed_ms}ms): {last_error}"
            )
        except Exception as exc:
            if cache_key:
                await self._fail_inflight(cache_key, exc)
            raise
        finally:
            if cache_key:
                await self._release_inflight(cache_key)

    async def _chat_stream(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        payload: Dict[str, Any],
    ) -> tuple[str, List[str], Dict[str, Any]]:
        chunks: List[str] = []
        text_parts: List[str] = []
        meta: Dict[str, Any] = {}
        async with client.stream("POST", "/chat/completions", headers=headers, json=payload) as response:
            response.raise_for_status()
            meta["response_id"] = response.headers.get("x-request-id") or response.headers.get("request-id")
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data:"):
                    data = line.removeprefix("data:").strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except Exception:
                        continue
                    meta["response_id"] = event.get("id") or meta.get("response_id")
                    usage = event.get("usage") or {}
                    if usage:
                        meta["tokens"] = {
                            "input": usage.get("prompt_tokens", 0),
                            "output": usage.get("completion_tokens", 0),
                        }
                    for choice in event.get("choices", []):
                        delta = choice.get("delta", {}) or {}
                        content = delta.get("content", "")
                        if content:
                            chunks.append(content)
                            text_parts.append(content)
        text = "".join(text_parts)
        meta.setdefault("tokens", {"input": 0, "output": 0})
        return text, chunks, meta

    def _normalize_response(
        self,
        data: Dict[str, Any],
        start: float,
        request_id: str,
        headers: httpx.Headers,
    ) -> Dict[str, Any]:
        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content")
        if not text and isinstance(choice.get("text"), str):
            text = choice.get("text")
        usage = data.get("usage") or {}
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        result = {
            "result": text or "",
            "content": text or "",
            "provider": self.provider_name,
            "model": self._model,
            "latency_ms": elapsed_ms,
            "cost": 0.0,
            "tokens": {
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
            },
            "request_id": headers.get("x-request-id") or headers.get("request-id") or request_id,
            "response_id": data.get("id") or headers.get("x-request-id") or request_id,
            "finish_reason": choice.get("finish_reason"),
            "domain": "general",
        }
        return result

    def _cache_key(
        self,
        messages: List[Message],
        max_tokens: int,
        temperature: float,
        response_format: Optional[Dict[str, Any]],
        cache_key_hint: Optional[str] = None,
    ) -> str:
        payload = {
            "provider": self.provider_name,
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": response_format,
            "cache_key_hint": cache_key_hint or "",
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="ignore")
        ).hexdigest()
        return f"{LLM_CACHE_PREFIX}{digest}"

    async def _get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            redis = await get_redis()
            raw = await redis.get(cache_key)
            if not raw:
                return None
            cached = json.loads(raw)
            if isinstance(cached, dict):
                return cached
        except Exception as exc:
            logger.debug("DeepSeek cache read failed: %s", exc)
        return None

    async def _set_cached_response(self, cache_key: str, response: Dict[str, Any]) -> None:
        try:
            redis = await get_redis()
            cacheable = dict(response)
            cacheable.pop("cached", None)
            cacheable.pop("parsed", None)
            await redis.setex(cache_key, self._cache_ttl_s, json.dumps(cacheable, default=str))
        except Exception as exc:
            logger.debug("DeepSeek cache write failed: %s", exc)

    async def _cooldown_remaining(self) -> float:
        try:
            redis = await get_redis()
            key = f"{LLM_COOLDOWN_PREFIX}{self.provider_name}:{self._model}"
            ttl = await redis.ttl(key)
            if ttl and ttl > 0:
                return float(ttl)
        except Exception as exc:
            logger.debug("DeepSeek cooldown check failed: %s", exc)
        return 0.0

    async def _set_cooldown(self, retry_after: Optional[str]) -> None:
        cooldown = float(self._cooldown_s)
        if retry_after:
            try:
                cooldown = max(cooldown, float(retry_after))
            except ValueError:
                pass
        try:
            redis = await get_redis()
            key = f"{LLM_COOLDOWN_PREFIX}{self.provider_name}:{self._model}"
            await redis.setex(key, int(max(1, cooldown)), "1")
            logger.warning(
                "DeepSeek cooldown activated",
                extra={
                    "provider": self.provider_name,
                    "model": self._model,
                    "cooldown_seconds": int(max(1, cooldown)),
                },
            )
        except Exception as exc:
            logger.debug("DeepSeek cooldown write failed: %s", exc)

    async def _acquire_inflight(self, cache_key: str) -> tuple[asyncio.Future, bool]:
        async with _inflight_lock:
            future = _inflight_requests.get(cache_key)
            if future is not None:
                return future, False
            future = asyncio.get_running_loop().create_future()
            _inflight_requests[cache_key] = future
            return future, True

    async def _release_inflight(self, cache_key: str) -> None:
        async with _inflight_lock:
            _inflight_requests.pop(cache_key, None)

    async def _fail_inflight(self, cache_key: str, exc: Exception) -> None:
        async with _inflight_lock:
            future = _inflight_requests.get(cache_key)
            if future is not None and not future.done():
                future.set_exception(exc)
                try:
                    future.exception()
                except Exception:
                    pass

    async def _succeed_inflight(self, cache_key: str, result: Dict[str, Any]) -> None:
        async with _inflight_lock:
            future = _inflight_requests.get(cache_key)
            if future is not None and not future.done():
                future.set_result(result)

    def _log_success(self, result: Dict[str, Any]) -> None:
        tokens = result.get("tokens", {})
        logger.info(
            "DeepSeek NIM response",
            extra={
                "provider": self.provider_name,
                "model": self._model,
                "request_id": result.get("request_id"),
                "response_id": result.get("response_id"),
                "latency_ms": result.get("latency_ms"),
                "prompt_tokens": tokens.get("input", 0),
                "completion_tokens": tokens.get("output", 0),
            },
        )

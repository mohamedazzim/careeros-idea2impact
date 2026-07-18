"""Base LLM provider contract for provider-agnostic generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type


Message = Dict[str, str]


class LLMProvider(ABC):
    """Abstract provider interface used by the orchestration layer."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def chat(
        self,
        messages: List[Message],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        stream: bool = False,
        response_format: Optional[Dict[str, Any]] = None,
        cache_key_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a chat-completions request and return normalized metadata."""

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_key_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        return await self.chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
            cache_key_hint=cache_key_hint,
        )

    async def structured_generate(
        self,
        system_prompt: str,
        user_message: str,
        output_schema: Type,
        max_tokens: int = 4096,
        temperature: float = 0.0,
        cache_key_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})
        response = await self.chat(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=False,
            response_format={"type": "json_object"},
            cache_key_hint=cache_key_hint or getattr(output_schema, "__name__", None),
        )

        parsed = None
        text = response.get("result", "")
        try:
            import json

            if hasattr(output_schema, "model_validate_json"):
                parsed = output_schema.model_validate_json(text)
            else:
                parsed = output_schema.parse_raw(text)  # type: ignore[attr-defined]
        except Exception:
            try:
                import json

                data = json.loads(text)
                if hasattr(output_schema, "model_validate"):
                    parsed = output_schema.model_validate(data)
                else:
                    parsed = output_schema.parse_obj(data)  # type: ignore[attr-defined]
            except Exception:
                parsed = None

        if parsed is not None:
            response["parsed"] = parsed
            response["result"] = parsed.model_dump() if hasattr(parsed, "model_dump") else parsed
        return response

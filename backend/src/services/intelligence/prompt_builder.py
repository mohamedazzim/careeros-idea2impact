"""
Modular prompt builder for Claude intelligence orchestration.

Composes prompts from registered templates, injects retrieval context,
citations, and metadata. Ensures deterministic, grounded formatting.

Stateless, async-safe, template-driven. Worker-safe.
"""
import logging
from typing import Dict, Any, Optional, List

from src.services.intelligence.prompt_versioning import get_active, _track_usage
from src.schemas.retrieval import Citation

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builds Claude-ready prompts from versioned templates with context injection."""

    async def build(
        self,
        category: str,
        prompt_id: str,
        template_vars: Dict[str, Any],
        retrieval_context: str = "",
        citations: Optional[List[Citation]] = None,
        guardrails: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a full prompt (system + human) from a registered template.

        Args:
            category: Prompt category (ats, scoring, recommendation, interview, reasoning, governance)
            prompt_id: Specific prompt identifier
            template_vars: Variables to format into the human template
            retrieval_context: Retrieved and compressed context to inject
            citations: Citation list for evidence tracking
            guardrails: Optional grounding/hallucination guard instructions

        Returns:
            Dict with system_prompt, human_message, prompt_version, citations_included
        """
        prompt = get_active(category, prompt_id)
        if not prompt:
            raise ValueError(
                f"No active prompt found for {category}:{prompt_id}"
            )

        _track_usage(prompt)

        # Build human message from template + retrieval context
        template_vars["retrieval_context"] = retrieval_context
        human = prompt.human_template.format(**template_vars)

        system = prompt.system_prompt

        # Inject guardrail instructions if provided
        if guardrails:
            guard_text = self._build_guardrail_text(guardrails)
            system += f"\n\n## Additional Guardrail Instructions\n{guard_text}"

        # Inject citation format instructions
        if citations:
            citation_text = self._format_citation_block(citations)
            system += f"\n\n## Available Evidence Citations\n{citation_text}\nReference citations by number in your response."

        return {
            "system_prompt": system,
            "human_message": human,
            "prompt_version": f"{prompt.prompt_id}:v{prompt.version}",
            "prompt_id": prompt.prompt_id,
            "category": category,
            "citations_included": len(citations) if citations else 0,
            "retrieval_context_length": len(retrieval_context),
        }

    def _build_guardrail_text(self, guardrails: Dict[str, Any]) -> str:
        parts = []
        for key, value in guardrails.items():
            parts.append(f"- {key}: {value}")
        return "\n".join(parts)

    def _format_citation_block(self, citations: List[Citation]) -> str:
        lines = []
        for c in citations:
            lines.append(
                f"[{c.citation_id}] Source: {c.source or 'unknown'} "
                f"(chunk: {c.chunk_id or 'N/A'})"
            )
        return "\n".join(lines)

    async def build_simple(
        self,
        system_prompt: str,
        human_message: str,
        retrieval_context: str = "",
    ) -> Dict[str, Any]:
        """Build a simple prompt without template registry (for testing/ad-hoc)."""
        return {
            "system_prompt": system_prompt,
            "human_message": human_message + f"\n\n<retrieval_context>\n{retrieval_context}\n</retrieval_context>",
            "prompt_version": "ad-hoc:v0",
            "prompt_id": "ad-hoc",
            "category": "uncategorized",
            "citations_included": 0,
            "retrieval_context_length": len(retrieval_context),
        }


_prompt_builder: Optional[PromptBuilder] = None


def get_prompt_builder() -> PromptBuilder:
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
    return _prompt_builder


def reset_prompt_builder() -> None:
    global _prompt_builder
    _prompt_builder = None


def __getattr__(name: str):
    if name == "prompt_builder":
        return get_prompt_builder()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

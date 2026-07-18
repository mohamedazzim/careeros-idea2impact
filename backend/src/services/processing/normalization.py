from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from langsmith import traceable
from pydantic import BaseModel, Field

from src.schemas.processing import NormalizedResumeData

logger = logging.getLogger(__name__)


class ResumeExtraction(BaseModel):
    name: str = Field(default="", description="The full name of the candidate")
    email: str = Field(default="", description="Email address")
    phone: str = Field(default="", description="Phone number")
    skills: List[str] = Field(default_factory=list, description="List of technical and soft skills")
    experience: List[Dict[str, Any]] = Field(default_factory=list, description="List of work experience entries")
    education: List[Dict[str, Any]] = Field(default_factory=list, description="List of education entries")
    projects: List[Dict[str, Any]] = Field(default_factory=list, description="List of projects")
    certifications: List[Dict[str, Any]] = Field(default_factory=list, description="List of certifications")
    summary: str = Field(default="", description="Professional summary")


class NormalizationService:
    def __init__(self):
        self.structured_llm = None

    @traceable(name="normalize_resume")
    async def normalize(self, text: str) -> NormalizedResumeData:
        if not text.strip():
            return NormalizedResumeData(personal_info={"status": "Failed configuration"})

        prompt = f"Extract the resume information from the following text carefully:\n\n{text}"

        try:
            extraction = None

            if self.structured_llm is not None:
                raw = await asyncio.to_thread(self.structured_llm.invoke, prompt)
                extraction = self._coerce_result(raw)
            else:
                from src.services.llm.factory import get_llm_provider

                provider = get_llm_provider()
                response = await provider.structured_generate(
                    system_prompt="You extract structured resume entities from raw resume text.",
                    user_message=prompt,
                    output_schema=ResumeExtraction,
                    max_tokens=1200,
                    temperature=0.0,
                )
                extraction = self._coerce_result(response.get("parsed") or response.get("result"))

            if not extraction:
                raise ValueError("Normalization returned no structured data")

            return NormalizedResumeData(
                personal_info={
                    "name": extraction.name,
                    "email": extraction.email,
                    "phone": extraction.phone,
                    "summary": extraction.summary,
                },
                experience=extraction.experience,
                education=extraction.education,
                skills=extraction.skills,
                projects=extraction.projects,
                certifications=extraction.certifications,
            )
        except Exception as e:
            logger.error(f"Error during LLM normalization: {e}")
            return NormalizedResumeData(
                personal_info={"status": "Extraction failed", "error": str(e)},
            )

    def _coerce_result(self, result: Any) -> ResumeExtraction | None:
        if result is None:
            return None
        if isinstance(result, ResumeExtraction):
            return result
        if isinstance(result, dict):
            if hasattr(ResumeExtraction, "model_validate"):
                try:
                    return ResumeExtraction.model_validate(result)
                except Exception:
                    return None
            try:
                return ResumeExtraction.parse_obj(result)  # type: ignore[attr-defined]
            except Exception:
                return None
        if hasattr(result, "model_dump"):
            try:
                dumped = result.model_dump()
                return ResumeExtraction.model_validate(dumped)
            except Exception:
                return None
        if hasattr(result, "__dict__"):
            try:
                return ResumeExtraction.model_validate(result.__dict__)
            except Exception:
                return None
        return None


normalization_service = NormalizationService()

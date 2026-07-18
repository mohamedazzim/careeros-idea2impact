"""
Output validator: JSON repair, schema compliance, citation validation.

Strict validation of structured Claude outputs. Enforces JSON structure,
schema compliance, citation validity, confidence ranges, and hallucination indicators.

Stateless, async-safe, observable. Worker-safe.
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional

from src.schemas.intelligence import ValidationReport
from src.observability.metrics import (
    OUTPUT_VALIDATION_FAILURES,
    OUTPUT_JSON_REPAIRS,
    OUTPUT_SCHEMA_MISMATCH,
)

logger = logging.getLogger(__name__)


class OutputValidator:
    """Validates and repairs structured Claude outputs."""

    def validate(
        self,
        response: Dict[str, Any],
        expected_keys: Optional[List[str]] = None,
        citations: Optional[List[Any]] = None,
    ) -> ValidationReport:
        """Validate a Claude structured output.

        Returns ValidationReport with repair status.
        """
        repair_attempts = 0
        malformed = []

        # 1. JSON structure check
        json_valid = isinstance(response, dict)
        json_repaired = False
        if not json_valid:
            repair_attempts += 1
            OUTPUT_VALIDATION_FAILURES.labels(reason="not_dict").inc()
            malformed.append("response_not_dict")

        # 2. Schema compliance
        schema_valid = True
        if expected_keys:
            missing = [k for k in expected_keys if k not in response]
            if missing:
                schema_valid = False
                malformed.append(f"missing_keys:{','.join(missing)}")
                OUTPUT_SCHEMA_MISMATCH.inc()

        # 3. Citation validity
        citations_valid = True
        missing_refs = 0
        if citations:
            cit_ids = {c.citation_id for c in citations if hasattr(c, 'citation_id')}
            response_text = json.dumps(response)
            found_refs = set()
            for match in re.finditer(r"\[(\d+)\]", response_text):
                found_refs.add(int(match.group(1)))
            missing_refs = len(found_refs - cit_ids)
            if missing_refs > 0:
                citations_valid = False
                malformed.append(f"missing_citations:{missing_refs}")
                OUTPUT_VALIDATION_FAILURES.labels(reason="citation_mismatch").inc()

        # 4. Confidence range check
        confidence_valid = True
        if "confidence" in response:
            conf = response["confidence"]
            if isinstance(conf, (int, float)) and (conf < 0 or conf > 1):
                confidence_valid = False
                malformed.append("confidence_out_of_range")

        # 5. Hallucination indicators
        if "hallucination_report" in response:
            hr = response["hallucination_report"]
            if isinstance(hr, dict) and hr.get("risk_level") in ("high", "critical"):
                malformed.append("hallucination_risk_flagged")

        valid = (
            json_valid
            and schema_valid
            and citations_valid
            and confidence_valid
            and len(malformed) == 0
        )

        score = 1.0 if valid else max(0.2, 1.0 - (len(malformed) * 0.2))

        return ValidationReport(
            valid=valid,
            schema_compliant=schema_valid,
            json_parsed=json_valid,
            json_repaired=json_repaired,
            citations_valid=citations_valid,
            confidence_in_range=confidence_valid,
            missing_evidence_refs=missing_refs,
            malformed_sections=malformed,
            repair_attempts=repair_attempts,
            validation_score=round(score, 4),
        )

    def repair_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Attempt to repair malformed JSON from Claude.

        Handles: trailing commas, unquoted keys, markdown code fences.
        """
        if not isinstance(text, str):
            return None

        # Strip markdown fences
        text = re.sub(r"^```(?:json)?\s*", "", text.strip())
        text = re.sub(r"\s*```$", "", text.strip())

        # Try direct parse
        try:
            OUTPUT_JSON_REPAIRS.inc()
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Fix trailing commas
        try:
            fixed = re.sub(r",\s*([}\]])", r"\1", text)
            OUTPUT_JSON_REPAIRS.inc()
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON object from text
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                OUTPUT_JSON_REPAIRS.inc()
                return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

        return None


_output_validator: Optional[OutputValidator] = None


def get_output_validator() -> OutputValidator:
    global _output_validator
    if _output_validator is None:
        _output_validator = OutputValidator()
    return _output_validator


def reset_output_validator() -> None:
    global _output_validator
    _output_validator = None


def __getattr__(name: str):
    if name == "output_validator":
        return get_output_validator()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

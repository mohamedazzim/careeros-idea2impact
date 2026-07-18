import re
import logging

logger = logging.getLogger(__name__)

# Basic PII regex for fallback if GLiNER isn't initialized
EMAIL_REGEX = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
PHONE_REGEX = r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
SSN_REGEX = r'\d{3}-\d{2}-\d{4}'

# Injection signatures
INJECTION_SIGNATURES = [
    "ignore previous instructions",
    "you are now",
    "forget everything",
    "system update:",
    "bypass constraints"
]

class AISecurityService:
    def __init__(self):
        # We wrap GLiNER lazy-loading to optimize import time
        self.gliner_model = None

    def _get_gliner(self):
        if self.gliner_model is None:
            try:
                from gliner import GLiNER
                self.gliner_model = GLiNER.from_pretrained("urchade/gliner_multi-v2.1")
            except Exception:
                logger.warning("GLiNER model unavailable, using Regex fallback for PII")
                return None
        return self.gliner_model

    def validate_prompt_injection(self, user_input: str) -> bool:
        """
        Validates whether the user input contains prompt injection patterns.
        """
        normalized_input = user_input.lower()
        if any(sig in normalized_input for sig in INJECTION_SIGNATURES):
            raise ValueError("Potential prompt injection detected")
        return True

    def sanitize_context_poisoning(self, context_chunks: list[str]) -> list[str]:
        """
        Ensures retrieved vectors don't contain malicious instruction overrides.
        """
        sanitized = []
        for chunk in context_chunks:
            # Strip markdown instruction formatting attempts
            clean_chunk = re.sub(r'```.*?```', '', chunk, flags=re.DOTALL)
            clean_chunk = re.sub(r'<instructions>.*?</instructions>', '', clean_chunk, flags=re.DOTALL | re.IGNORECASE)
            sanitized.append(clean_chunk)
        return sanitized

    def redact_pii(self, text: str) -> str:
        """
        Detects and redacts PII using GLiNER (if available) and regex.
        """
        redacted = text
        
        # Regex baseline
        redacted = re.sub(EMAIL_REGEX, "[REDACTED_EMAIL]", redacted)
        redacted = re.sub(PHONE_REGEX, "[REDACTED_PHONE]", redacted)
        redacted = re.sub(SSN_REGEX, "[REDACTED_NATIONAL_ID]", redacted)

        gliner = self._get_gliner()
        if gliner:
            labels = ["address", "person", "credit card"]
            entities = gliner.predict_entities(redacted, labels)
            
            # Sub from string end to start to not mess up offsets
            entities.sort(key=lambda x: x["start"], reverse=True)
            for ent in entities:
                start = ent["start"]
                end = ent["end"]
                label = ent["label"].upper()
                redacted = redacted[:start] + f"[REDACTED_{label}]" + redacted[end:]
                
        return redacted

ai_security = AISecurityService()

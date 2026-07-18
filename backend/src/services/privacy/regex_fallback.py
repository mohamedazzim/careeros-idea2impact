import re
from typing import List, Dict, Any

REGEX_PATTERNS = {
    "email": r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+',
    "phone": r'(\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}',
    "linkedin": r'(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+',
    "github": r'(?:https?:\/\/)?(?:www\.)?github\.com\/[a-zA-Z0-9_-]+',
}

def detect_pii_regex(text: str) -> List[Dict[str, Any]]:
    entities = []
    for category, pattern in REGEX_PATTERNS.items():
        for match in re.finditer(pattern, text, re.IGNORECASE):
            entities.append({
                "category": category,
                "text": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "confidence": 0.85, # Base confidence for regex matching
                "source": "regex"
            })
    return entities

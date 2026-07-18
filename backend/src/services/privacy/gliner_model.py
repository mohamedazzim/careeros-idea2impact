from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

gliner_model = None
GLiNER = None
_model_loaded = False


def _ensure_model():
    """Lazy-load the GLiNER model on first use with timeout."""
    global gliner_model, GLiNER, _model_loaded
    if _model_loaded:
        return
    _model_loaded = True
    try:
        from gliner import GLiNER as _GLiNER
        GLiNER = _GLiNER
    except ImportError:
        logger.warning("gliner package not installed — GLiNER NER will use regex fallback only")
        gliner_model = None
        return

    # Check for offline/testing mode
    import os
    if os.getenv("MOCK_GLINER", "").lower() == "true" or os.getenv("CI", "").lower() == "true":
        logger.info("MOCK_GLINER or CI mode: skipping model download")
        gliner_model = None
        return

    try:
        gliner_model = GLiNER.from_pretrained("urchade/gliner_small-v2.1")
        logger.info("GLiNER model loaded successfully")
    except Exception as e:
        logger.warning(f"Failed to load GLiNER model (will use regex fallback): {e}")
        gliner_model = None


# We can query these categories in gliner
LABELS = ["person", "email", "phone number", "address", "organization", "url"]

LABEL_MAP = {
    "person": "name",
    "email": "email",
    "phone number": "phone",
    "address": "address",
    "url": "linkedin"
}


def detect_pii_gliner(text: str) -> List[Dict[str, Any]]:
    _ensure_model()
    if not gliner_model:
        return []

    try:
        predictions = gliner_model.predict_entities(text, LABELS, threshold=0.5)
        entities = []
        for pred in predictions:
            cat = LABEL_MAP.get(pred["label"], pred["label"])
            if cat == "linkedin" and "github" in pred["text"].lower():
                cat = "github"

            entities.append({
                "category": cat,
                "text": pred["text"],
                "start": pred["start"],
                "end": pred["end"],
                "confidence": pred.get("score", 0.7),
                "source": "gliner"
            })
        return entities
    except Exception as e:
        logger.error(f"GLiNER prediction error: {e}")
        return []

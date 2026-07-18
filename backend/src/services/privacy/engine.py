from typing import List, Tuple
from src.schemas.privacy import PIIEntity, PIIAuditReport
from .gliner_model import detect_pii_gliner
from .regex_fallback import detect_pii_regex
from langsmith import traceable

class PrivacyEngine:
    def __init__(self):
        pass

    @traceable(name="detect_pii_entities")
    def detect_entities(self, text: str) -> List[PIIEntity]:
        # 1. Primary: GLiNER
        gliner_entities = detect_pii_gliner(text)
        
        # 2. Secondary: Regex
        regex_entities = detect_pii_regex(text)
        
        # Merge entities, resolving overlaps (prefer higher confidence)
        all_entities = gliner_entities + regex_entities
        all_entities.sort(key=lambda x: x["start"])
        
        merged = []
        for ent in all_entities:
            if not merged:
                merged.append(ent)
            else:
                last_ent = merged[-1]
                # Check for overlap
                if ent["start"] < last_ent["end"]:
                    if ent["confidence"] > last_ent["confidence"]:
                        merged[-1] = ent # replace with higher confidence
                else:
                    merged.append(ent)
                    
        return [PIIEntity(**e) for e in merged]

    def mask_text(self, text: str, entities: List[PIIEntity]) -> str:
        # Replace from end to start to avoid index shifting problems
        sorted_entities = sorted(entities, key=lambda x: x.start, reverse=True)
        masked_text = text
        for ent in sorted_entities:
            masked_text = masked_text[:ent.start] + f"[{ent.category.upper()}]" + masked_text[ent.end:]
        return masked_text

    @traceable(name="process_privacy_masking")
    def process(self, text: str) -> Tuple[str, PIIAuditReport]:
        import os
        
        tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        # We can implement LangSmith @traceable decorators in production
        
        entities = self.detect_entities(text)
        masked_text = self.mask_text(text, entities)
        
        cat_counts = {}
        for e in entities:
            cat_counts[e.category] = cat_counts.get(e.category, 0) + 1
            
        report = PIIAuditReport(
            total_entities_found=len(entities),
            categories_found=cat_counts,
            entities=entities,
            original_text_length=len(text),
            masked_text_length=len(masked_text)
        )
        
        return masked_text, report

privacy_engine = PrivacyEngine()

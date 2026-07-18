from pydantic import BaseModel, Field
from typing import List, Dict

class PIIEntity(BaseModel):
    category: str
    text: str
    start: int
    end: int
    confidence: float
    source: str = Field(description="gliner or regex")

class PIIAuditReport(BaseModel):
    total_entities_found: int
    categories_found: Dict[str, int]
    entities: List[PIIEntity]
    original_text_length: int
    masked_text_length: int

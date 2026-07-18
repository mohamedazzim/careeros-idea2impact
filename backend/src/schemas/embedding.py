from pydantic import BaseModel
from typing import Optional

class EmbeddingsGenerationResponse(BaseModel):
    dimensions: int
    model_name: str
    chunks_processed: int
    status: str
    error: Optional[str] = None

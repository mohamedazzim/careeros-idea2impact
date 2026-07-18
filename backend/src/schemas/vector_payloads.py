from pydantic import BaseModel
from typing import Optional

class ResumePayload(BaseModel):
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    chunk_index: int
    text: str
    source: Optional[str] = None
    version_num: int
    created_at: Optional[str] = None
    # Backward compatibility
    user_id: Optional[str] = None
    resume_id: Optional[int] = None
    start_char: Optional[int] = 0
    end_char: Optional[int] = 0

class JobPayload(BaseModel):
    job_id: str
    company: str
    title: str
    text: str
    source: Optional[str] = None
    version_num: Optional[int] = None

class KnowledgePayload(BaseModel):
    document_id: str
    category: str
    text: str
    source: Optional[str] = None
    version_num: Optional[int] = None

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class ResumeChunkData(BaseModel):
    chunk_index: int
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ExtractedResumeData(BaseModel):
    raw_text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class NormalizedResumeData(BaseModel):
    personal_info: Dict[str, Any] = Field(default_factory=dict)
    experience: List[Dict[str, Any]] = Field(default_factory=list)
    education: List[Dict[str, Any]] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    certifications: List[Dict[str, Any]] = Field(default_factory=list)

class VersionRecord(BaseModel):
    version_num: int
    resume_id: int
    raw_content: Optional[str] = None
    masked_content: Optional[str] = None
    normalized_content: Optional[Dict[str, Any]] = None

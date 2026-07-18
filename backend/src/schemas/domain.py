from pydantic import BaseModel
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    email: str
    target_role: Optional[str] = None

class User(UserBase):
    id: str
    created_at: datetime
    class Config:
        from_attributes = True

class UserPreferences(BaseModel):
    alert_threshold: int = 85
    notification_email: Optional[str] = None
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "08:00"
    enable_twilio_alerts: bool = False
    enable_linkedin_posts: bool = False
    target_role: Optional[str] = None
    target_salary: Optional[str] = None
    target_location: Optional[str] = None
    experience_level: Optional[str] = None
    career_stage: Optional[str] = None
    preferred_work_mode: Optional[str] = None
    timeline_months: Optional[int] = None

# Knowledge & Documents
class KnowledgeDoc(BaseModel):
    id: str
    user_id: str
    filename: str
    doc_type: Literal['resume', 'doc', 'cover_letter']
    raw_text: str
    cleaned_text: str
    status: Literal['uploaded', 'ingested', 'stripping_pii', 'embedding', 'indexed', 'failed']
    created_at: datetime

class JobSkill(BaseModel):
    skill: str
    importance: Literal['high', 'medium', 'low']

class Job(BaseModel):
    id: str
    source: str
    external_id: str
    title: str
    company: str
    location: str
    employment_type: str
    description: str
    apply_url: str
    posted_at: datetime
    created_at: datetime
    skills: List[JobSkill] = []

class Strength(BaseModel):
    title: str
    impact: Literal['high', 'medium', 'low']
    description: str

class Gap(BaseModel):
    category: str
    severity: Literal['high', 'medium', 'low']
    description: str
    suggestion: str

class MatchResult(BaseModel):
    match_score: int
    grade: str
    strengths: List[Strength]
    gaps: List[Gap]
    summary: str
    recommendations: List[str]

class ApplicationPackage(BaseModel):
    id: str
    user_id: str
    job_id: str
    status: Literal['processing', 'completed', 'failed']
    created_at: datetime
    updated_at: datetime
    summary_sheet: Optional[Dict[str, Any]] = None

class InterviewSession(BaseModel):
    id: str
    user_id: str
    job_id: str
    interview_type: str
    status: Literal['processing', 'ongoing', 'completed', 'failed']
    started_at: datetime
    ended_at: Optional[datetime] = None
    overall_score: Optional[int] = None
    topics: List[str] = []

class Roadmap(BaseModel):
    id: str
    user_id: str
    roadmap_type: str
    title: str
    summary: str
    status: Literal['draft', 'active', 'completed', 'archived']
    created_at: datetime
    updated_at: datetime

class RoadmapGoal(BaseModel):
    id: str
    roadmap_id: str
    goal_type: str
    title: str
    description: str
    target_date: datetime
    status: Literal['pending', 'in_progress', 'completed']

class Approval(BaseModel):
    id: str
    user_id: str
    approval_type: str
    status: Literal['draft', 'pending', 'approved', 'rejected', 'executed', 'archived']
    title: str
    summary: str
    payload_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

class OpportunityAlert(BaseModel):
    id: str
    user_id: str
    job_id: str
    alert_type: str
    status: Literal['pending', 'approved', 'rejected', 'dismissed']
    match_score: Optional[int] = None
    created_at: datetime
    notes: Optional[str] = None

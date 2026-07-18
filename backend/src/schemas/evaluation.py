from pydantic import BaseModel, Field
from typing import List

class ATSScore(BaseModel):
    score: int = Field(..., ge=0, le=100, description="Overall ATS compatibility score")
    justification: str = Field(..., description="Explanation of the ATS score and how it was calculated")

class MatchScore(BaseModel):
    score: int = Field(..., ge=0, le=100, description="Overall alignment score between resume and job")
    strongest_factors: List[str] = Field(..., description="Strongest alignment factors")
    weakest_factors: List[str] = Field(..., description="Weakest alignment factors")
    rationale: str = Field(..., description="Explanation of the match score rationale")

class Strength(BaseModel):
    strength: str = Field(..., description="The identified strength")
    evidence: str = Field(..., description="Evidence from the resume supporting this strength")
    impact: str = Field(..., description="Impact of this strength for the job requirements")
    confidence_score: float = Field(..., ge=0.0, le=1.0)

class Weakness(BaseModel):
    weakness: str = Field(..., description="The identified weakness or missing qualification")
    evidence: str = Field(..., description="Evidence (or lack thereof) from the resume")
    impact: str = Field(..., description="Impact of this weakness on job performance")
    confidence_score: float = Field(..., ge=0.0, le=1.0)

class Recommendation(BaseModel):
    priority: str = Field(..., description="Priority level (High, Medium, Low)")
    category: str = Field(..., description="Category (skills, projects, certifications, resume improvements, interview preparation)")
    recommendation: str = Field(..., description="Actionable recommendation")
    expected_impact: str = Field(..., description="Expected impact of implementing this recommendation")

class SkillGap(BaseModel):
    skill: str = Field(..., description="The specific skill")
    status: str = Field(..., description="Status (Required Skills Present, Required Skills Missing, Nice-to-Have Skills Present, Nice-to-Have Skills Missing)")
    importance: str = Field(..., description="Importance level of the skill")
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str = Field(..., description="Explicit evidence mapping from context or 'Not Found In Resume'")

class ResumeEvaluation(BaseModel):
    ats_score: ATSScore
    match_score: MatchScore
    strengths: List[Strength]
    weaknesses: List[Weakness]
    recommendations: List[Recommendation]
    skill_gaps: List[SkillGap]

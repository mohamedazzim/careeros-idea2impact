from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

class CareerOSState(TypedDict):
    user_id: Optional[str]
    resume_id: Optional[str]
    job_id: Optional[str]
    
    resume_data: Optional[Dict[str, Any]]
    job_data: Optional[Dict[str, Any]]
    
    retrieved_context: Optional[str]
    
    evaluation_result: Optional[Dict[str, Any]]
    recommendations: Optional[List[Dict[str, Any]]]
    report: Optional[Dict[str, Any]]
    opportunity_alert: Optional[bool]
    
    errors: List[str]
    metadata: Dict[str, Any]
    execution_metrics: Dict[str, float]
    
    graph_version: str
    timestamp: float
    retries: Dict[str, int]

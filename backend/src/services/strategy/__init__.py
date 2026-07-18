"""
Career Strategy Intelligence — Phase 4C.

Production Claude Sonnet 4.6 integration with:
- Career trajectory analysis
- Personalized learning paths
- Architecture maturity evaluation
- AI engineering readiness
- Hiring probability estimation
- Portfolio strategy
- Recruiter visibility
- Opportunity prioritization
- Strategic roadmap generation
- Confidence calibration + observability

Stateless, async-safe, LangGraph-compatible, governance-ready.
"""
from .career_trajectory_service import CareerTrajectoryService
from .learning_path_service import LearningPathService
from .architecture_maturity_service import ArchitectureMaturityService
from .ai_readiness_service import AIReadinessService
from .hiring_probability_service import HiringProbabilityService
from .portfolio_strategy_service import PortfolioStrategyService
from .recruiter_visibility_service import RecruiterVisibilityService
from .opportunity_prioritization_service import OpportunityPrioritizationService
from .growth_gap_service import GrowthGapService
from .strategic_reasoning_service import StrategicReasoningService
from .roadmap_generation_service import RoadmapGenerationService
from .milestone_planning_service import MilestonePlanningService
from .market_alignment_service import MarketAlignmentService
from .strategic_confidence_engine import StrategicConfidenceEngine
from .strategy_observability import StrategyObservability

__all__ = [
    "CareerTrajectoryService",
    "LearningPathService",
    "ArchitectureMaturityService",
    "AIReadinessService",
    "HiringProbabilityService",
    "PortfolioStrategyService",
    "RecruiterVisibilityService",
    "OpportunityPrioritizationService",
    "GrowthGapService",
    "StrategicReasoningService",
    "RoadmapGenerationService",
    "MilestonePlanningService",
    "MarketAlignmentService",
    "StrategicConfidenceEngine",
    "StrategyObservability",
    "career_trajectory_service", "learning_path_service",
    "architecture_maturity_service", "ai_readiness_service",
    "hiring_probability_service", "portfolio_strategy_service",
    "recruiter_visibility_service", "opportunity_prioritization_service",
    "growth_gap_service", "strategic_reasoning_service",
    "roadmap_generation_service", "milestone_planning_service",
    "market_alignment_service", "strategic_confidence_engine",
    "strategy_observability",
]

def __getattr__(name: str):
    m = {
        "career_trajectory_service": ".career_trajectory_service",
        "learning_path_service": ".learning_path_service",
        "architecture_maturity_service": ".architecture_maturity_service",
        "ai_readiness_service": ".ai_readiness_service",
        "hiring_probability_service": ".hiring_probability_service",
        "portfolio_strategy_service": ".portfolio_strategy_service",
        "recruiter_visibility_service": ".recruiter_visibility_service",
        "opportunity_prioritization_service": ".opportunity_prioritization_service",
        "growth_gap_service": ".growth_gap_service",
        "strategic_reasoning_service": ".strategic_reasoning_service",
        "roadmap_generation_service": ".roadmap_generation_service",
        "milestone_planning_service": ".milestone_planning_service",
        "market_alignment_service": ".market_alignment_service",
        "strategic_confidence_engine": ".strategic_confidence_engine",
        "strategy_observability": ".strategy_observability",
    }
    if name in m:
        mod = __import__(f"src.services.strategy{m[name]}", fromlist=[None])
        return getattr(mod, f"get_{name}")()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

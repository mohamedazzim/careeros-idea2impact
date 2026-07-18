"""Learning-path services for verified skill gaps."""

from .learning_resource_service import LearningResourceService, get_learning_resource_service, is_real_http_url
from .gap_action_service import LearningGapActionService, get_learning_gap_action_service
from .github_project_service import GitHubProjectService, get_github_project_service
from .learning_path_service import LearningPathService, get_learning_path_service
from .learning_outcome_service import LearningOutcomeService, get_learning_outcome_service
from .resource_provenance_service import ResourceProvenanceService, get_resource_provenance_service
from .skill_normalizer import NormalizedSkill, canonical_display_name, normalize_skill, normalize_skill_list, skill_search_terms, slugify_skill

__all__ = [
    "LearningResourceService",
    "LearningPathService",
    "LearningGapActionService",
    "GitHubProjectService",
    "LearningOutcomeService",
    "ResourceProvenanceService",
    "NormalizedSkill",
    "canonical_display_name",
    "get_learning_gap_action_service",
    "get_github_project_service",
    "get_learning_path_service",
    "get_learning_outcome_service",
    "get_resource_provenance_service",
    "get_learning_resource_service",
    "is_real_http_url",
    "normalize_skill",
    "normalize_skill_list",
    "skill_search_terms",
    "slugify_skill",
]

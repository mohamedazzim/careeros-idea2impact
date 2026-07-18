"""GitHub discovery integration for learning gap project recommendations."""

from .repo_discovery import (
    GitHubDiscoveryError,
    GitHubIssueCandidate,
    GitHubProjectDiscoveryProvider,
    GitHubRateLimitError,
    GitHubRepositoryCandidate,
    GitHubSkillDiscoveryResult,
    get_github_project_discovery_provider,
)

__all__ = [
    "GitHubDiscoveryError",
    "GitHubIssueCandidate",
    "GitHubProjectDiscoveryProvider",
    "GitHubRateLimitError",
    "GitHubRepositoryCandidate",
    "GitHubSkillDiscoveryResult",
    "get_github_project_discovery_provider",
]

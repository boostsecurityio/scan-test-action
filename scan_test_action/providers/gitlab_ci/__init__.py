"""GitLab CI provider module."""

from scan_test_action.providers.gitlab_ci.config import GitLabCIConfig
from scan_test_action.providers.gitlab_ci.provider import GitLabCIProvider

__all__ = ["GitLabCIConfig", "GitLabCIProvider"]

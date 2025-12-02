"""GitHub Actions provider module."""

from scan_test_action.providers.github_actions.config import GitHubActionsConfig
from scan_test_action.providers.github_actions.manifest import github_actions_manifest
from scan_test_action.providers.github_actions.provider import GitHubActionsProvider

__all__ = ["GitHubActionsConfig", "GitHubActionsProvider", "github_actions_manifest"]

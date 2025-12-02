"""GitHub Actions provider manifest."""

from scan_test_action.providers.github_actions.config import GitHubActionsConfig
from scan_test_action.providers.github_actions.provider import GitHubActionsProvider
from scan_test_action.providers.manifest import ProviderManifest

github_actions_manifest = ProviderManifest(
    config_cls=GitHubActionsConfig,
    provider_factory=GitHubActionsProvider.from_config,
)

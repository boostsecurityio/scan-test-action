"""GitLab CI provider manifest."""

from scan_test_action.providers.gitlab_ci.config import GitLabCIConfig
from scan_test_action.providers.gitlab_ci.provider import GitLabCIProvider
from scan_test_action.providers.manifest import ProviderManifest

gitlab_ci_manifest = ProviderManifest(
    config_cls=GitLabCIConfig,
    provider_factory=GitLabCIProvider.from_config,
)

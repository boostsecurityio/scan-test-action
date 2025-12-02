"""Bitbucket Pipelines provider manifest."""

from scan_test_action.providers.bitbucket.config import BitbucketConfig
from scan_test_action.providers.bitbucket.provider import BitbucketProvider
from scan_test_action.providers.manifest import ProviderManifest

bitbucket_manifest = ProviderManifest(
    config_cls=BitbucketConfig,
    provider_factory=BitbucketProvider.from_config,
)

"""Azure DevOps provider manifest."""

from scan_test_action.providers.azure_devops.config import AzureDevOpsConfig
from scan_test_action.providers.azure_devops.provider import AzureDevOpsProvider
from scan_test_action.providers.manifest import ProviderManifest

azure_devops_manifest = ProviderManifest(
    config_cls=AzureDevOpsConfig,
    provider_factory=AzureDevOpsProvider.from_config,
)

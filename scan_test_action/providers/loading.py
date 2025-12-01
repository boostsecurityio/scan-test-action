"""Loading of providers from entry points."""

from importlib.metadata import entry_points
from typing import Any

from scan_test_action.providers.manifest import ProviderManifest

ENTRY_POINT_GROUP = "scan_test_action.providers"


class ProviderNotFoundError(Exception):
    """Raised when a provider is not found."""


def load_provider_manifest(key: str) -> ProviderManifest[Any, Any]:
    """Load a provider manifest by key.

    Args:
        key: The provider key as registered in pyproject.toml
             (e.g., "github-actions", "gitlab-ci")

    Returns:
        The provider manifest instance

    Raises:
        ProviderNotFoundError: If no provider with the given key is found

    """
    entries = entry_points(group=ENTRY_POINT_GROUP)

    for entry in entries:
        if entry.name == key:
            manifest: ProviderManifest[Any, Any] = entry.load()
            return manifest

    available = [e.name for e in entries]
    raise ProviderNotFoundError(
        f"Provider '{key}' not found. Available providers: {available}"
    )

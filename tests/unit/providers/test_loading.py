"""Tests for provider loading module."""

import pytest

from scan_test_action.providers.github_actions import github_actions_manifest
from scan_test_action.providers.loading import (
    ProviderNotFoundError,
    load_provider_manifest,
)


def test_load_provider_manifest_returns_manifest() -> None:
    """Loads provider manifest by key."""
    manifest = load_provider_manifest("github-actions")

    assert manifest is github_actions_manifest


def test_load_provider_manifest_raises_for_unknown_provider() -> None:
    """Raises ProviderNotFoundError for unknown provider key."""
    with pytest.raises(ProviderNotFoundError) as exc_info:
        load_provider_manifest("unknown-provider")

    assert "unknown-provider" in str(exc_info.value)
    assert "Available providers" in str(exc_info.value)

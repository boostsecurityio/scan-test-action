"""Provider manifest definition for the plugin system."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from pydantic import BaseModel

from scan_test_action.providers.base import PipelineProvider


@dataclass(frozen=True, kw_only=True)
class ProviderManifest[ConfigT: BaseModel, StateT]:
    """Manifest describing a provider plugin.

    The manifest contains references to the configuration class and the
    provider factory function for lazy loading of providers based on their key.
    """

    config_cls: type[ConfigT]
    provider_factory: Callable[
        [ConfigT], AbstractAsyncContextManager[PipelineProvider[StateT]]
    ]

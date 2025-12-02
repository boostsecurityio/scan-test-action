"""Configuration for GitHub Actions provider."""

from typing import Literal

from pydantic import BaseModel, SecretStr


class GitHubActionsConfig(BaseModel):
    """Configuration for GitHub Actions provider."""

    token: SecretStr
    owner: str
    repo: str
    workflow_id: str
    ref: str = "main"
    api_base_url: str = "https://api.github.com"
    # Use "static" for deterministic dispatch_id in module tests with WireMock
    dispatch_id_mode: Literal["random", "static"] = "random"

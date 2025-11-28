"""Configuration for GitHub Actions provider."""

from pydantic import BaseModel, SecretStr


class GitHubActionsConfig(BaseModel):
    """Configuration for GitHub Actions provider."""

    token: SecretStr
    owner: str
    repo: str
    workflow_id: str
    ref: str = "main"
    api_base_url: str = "https://api.github.com"

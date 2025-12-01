"""Configuration for GitLab CI provider."""

from pydantic import BaseModel, SecretStr


class GitLabCIConfig(BaseModel):
    """Configuration for GitLab CI provider."""

    token: SecretStr
    project_id: str
    ref: str = "main"
    api_base_url: str = "https://gitlab.com/api/v4/"

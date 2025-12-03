"""Configuration for GitLab CI provider."""

from pydantic import BaseModel, SecretStr


class GitLabCIConfig(BaseModel):
    """Configuration for GitLab CI provider.

    Uses two separate tokens with minimal privileges:
    - trigger_token: Pipeline Trigger Token for dispatching pipelines
    - api_token: Project Access Token (Guest role, read_api scope) for polling status
    """

    trigger_token: SecretStr
    api_token: SecretStr
    project_id: str
    ref: str = "main"
    api_base_url: str = "https://gitlab.com/api/v4/"

"""Configuration for Bitbucket Pipelines provider."""

from pydantic import BaseModel, SecretStr


class BitbucketConfig(BaseModel):
    """Configuration for Bitbucket Pipelines provider."""

    token: SecretStr
    workspace: str
    repo_slug: str
    branch: str = "main"
    api_base_url: str = "https://api.bitbucket.org/2.0/"

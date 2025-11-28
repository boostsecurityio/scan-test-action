"""Configuration for Azure DevOps provider."""

from pydantic import BaseModel, SecretStr


class AzureDevOpsConfig(BaseModel):
    """Configuration for Azure DevOps provider."""

    token: SecretStr
    organization: str
    project: str
    pipeline_id: int
    api_base_url: str = "https://dev.azure.com"

"""Base model configuration for all data structures."""

from pydantic import BaseModel, ConfigDict


class Model(BaseModel):
    """Base model with standard configuration."""

    model_config = ConfigDict(frozen=True)

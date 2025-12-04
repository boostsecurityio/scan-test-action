"""Pydantic models for Bitbucket Pipelines API responses."""

from datetime import datetime

from pydantic import BaseModel


class PipelineResult(BaseModel):
    """Result of a completed pipeline."""

    name: str  # e.g., SUCCESSFUL, FAILED, ERROR, STOPPED


class PipelineState(BaseModel):
    """State of a pipeline."""

    # Bitbucket API state values are poorly documented. Known values include:
    # PENDING, IN_PROGRESS, COMPLETED, STOPPED, ERROR, FAILED, PAUSED, PARSING
    name: str
    result: PipelineResult | None = None


class Pipeline(BaseModel):
    """A pipeline from Bitbucket API."""

    uuid: str
    build_number: int
    state: PipelineState
    created_on: datetime
    completed_on: datetime | None = None


class PipelineCreateResponse(BaseModel):
    """Response from pipeline creation."""

    uuid: str

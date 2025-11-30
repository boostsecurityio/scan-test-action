"""Pydantic models for Bitbucket Pipelines API responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

type PipelineStateName = Literal[
    "PENDING",
    "IN_PROGRESS",
    "COMPLETED",
    "STOPPED",
    "ERROR",
    "FAILED",
    "PAUSED",
]

type PipelineResultName = Literal[
    "SUCCESSFUL",
    "FAILED",
    "ERROR",
    "STOPPED",
]


class PipelineResult(BaseModel):
    """Result of a completed pipeline."""

    name: PipelineResultName


class PipelineState(BaseModel):
    """State of a pipeline."""

    name: PipelineStateName
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

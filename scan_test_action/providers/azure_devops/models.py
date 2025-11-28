"""Pydantic models for Azure DevOps API responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

type PipelineRunState = Literal[
    "unknown",
    "canceling",
    "completed",
    "inProgress",
]

type PipelineRunResult = Literal[
    "unknown",
    "canceled",
    "failed",
    "succeeded",
]


class WebLink(BaseModel):
    """Web link in _links."""

    href: str


class RunLinks(BaseModel):
    """Links in pipeline run response."""

    web: WebLink | None = None


class PipelineRun(BaseModel):
    """A pipeline run from Azure DevOps API."""

    id: int
    name: str
    state: PipelineRunState
    result: PipelineRunResult | None = None
    created_date: datetime = Field(alias="createdDate")
    finished_date: datetime | None = Field(default=None, alias="finishedDate")
    links: RunLinks | None = Field(default=None, alias="_links")

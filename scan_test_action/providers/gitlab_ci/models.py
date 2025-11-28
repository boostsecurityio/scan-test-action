"""Pydantic models for GitLab CI API responses."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

type PipelineStatus = Literal[
    "created",
    "waiting_for_resource",
    "preparing",
    "pending",
    "running",
    "success",
    "failed",
    "canceled",
    "skipped",
    "manual",
    "scheduled",
]


class Pipeline(BaseModel):
    """A pipeline from GitLab CI API."""

    id: int
    status: PipelineStatus
    ref: str
    web_url: str
    created_at: datetime
    updated_at: datetime

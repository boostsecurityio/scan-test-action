"""Pydantic models for GitHub Actions API responses."""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

type WorkflowConclusion = Literal[
    "success",
    "failure",
    "cancelled",
    "timed_out",
    "action_required",
    "neutral",
    "skipped",
    "stale",
]


class WorkflowRun(BaseModel):
    """A workflow run from GitHub Actions API."""

    id: int
    status: Literal["queued", "in_progress", "completed"]
    conclusion: WorkflowConclusion | None = None
    name: str
    display_title: str
    html_url: str
    created_at: datetime
    updated_at: datetime


class WorkflowRunsResponse(BaseModel):
    """Response from list workflow runs API."""

    workflow_runs: Sequence[WorkflowRun]

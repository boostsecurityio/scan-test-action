"""GitHub Actions provider implementation."""

import json
import logging
import uuid
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

import aiohttp

from scan_test_action.models.definition import TestDefinition
from scan_test_action.models.result import TestResult
from scan_test_action.providers.base import PipelineProvider
from scan_test_action.providers.github_actions.config import GitHubActionsConfig
from scan_test_action.providers.github_actions.models import (
    WorkflowConclusion,
    WorkflowRun,
    WorkflowRunsResponse,
)

log = logging.getLogger(__name__)

CONCLUSION_TO_STATUS: Mapping[
    WorkflowConclusion | None, Literal["success", "failure", "timeout", "error"]
] = {
    "success": "success",
    "failure": "failure",
    "cancelled": "error",
    "timed_out": "timeout",
    "action_required": "error",
    "neutral": "success",
    "skipped": "error",
    "stale": "error",
    None: "error",
}


@dataclass(frozen=True, kw_only=True)
class DispatchState:
    """State returned from dispatch for polling."""

    dispatch_id: str
    dispatch_time: datetime


@dataclass(frozen=True, kw_only=True)
class GitHubActionsProvider(PipelineProvider[DispatchState]):
    """GitHub Actions pipeline provider."""

    config: GitHubActionsConfig
    session: aiohttp.ClientSession = field(repr=False)

    @classmethod
    @asynccontextmanager
    async def from_config(
        cls, config: GitHubActionsConfig
    ) -> AsyncGenerator["GitHubActionsProvider", None]:
        """Create provider with managed session lifecycle."""
        headers = {
            "Authorization": f"Bearer {config.token.get_secret_value()}",
            "Accept": "application/vnd.github+json",
        }
        async with aiohttp.ClientSession(
            base_url=config.api_base_url,
            headers=headers,
        ) as session:
            yield cls(config=config, session=session)

    async def dispatch_scanner_tests(
        self,
        scanner_id: str,
        test_definition: TestDefinition,
        registry_ref: str,
        registry_repo: str,
    ) -> DispatchState:
        """Dispatch workflow and return state for polling."""
        if self.config.dispatch_id_mode == "static":
            dispatch_id = "static-dispatch-id"
        else:
            dispatch_id = str(uuid.uuid4())
        dispatch_time = datetime.now(timezone.utc)

        matrix_entries = [
            {"test_name": test.name, "scan_path": path}
            for test in test_definition.tests
            for path in test.scan_paths
        ]

        url = (
            f"/repos/{self.config.owner}/{self.config.repo}"
            f"/actions/workflows/{self.config.workflow_id}/dispatches"
        )
        payload = {
            "ref": self.config.ref,
            "inputs": {
                "dispatch_id": dispatch_id,
                "scanner_id": scanner_id,
                "registry_ref": registry_ref,
                "registry_repo": registry_repo,
                "matrix": json.dumps(matrix_entries),
            },
        }

        log.info(
            "Dispatching workflow: api_base_url=%s, url=%s, owner=%s, repo=%s, "
            "workflow_id=%s, ref=%s, scanner_id=%s, registry_ref=%s, registry_repo=%s",
            self.config.api_base_url,
            url,
            self.config.owner,
            self.config.repo,
            self.config.workflow_id,
            self.config.ref,
            scanner_id,
            registry_ref,
            registry_repo,
        )

        async with self.session.post(url, json=payload) as response:
            if response.status != 204:
                text = await response.text()
                raise RuntimeError(
                    f"Failed to dispatch workflow: {response.status} {text}"
                )

        return DispatchState(dispatch_id=dispatch_id, dispatch_time=dispatch_time)

    async def poll_status(
        self, dispatch_state: DispatchState
    ) -> Sequence[TestResult] | None:
        """Check if workflow is complete and return results."""
        run = await self.find_workflow_run(
            dispatch_state.dispatch_id, dispatch_state.dispatch_time
        )
        if run is None:
            log.info(
                "Workflow run not found for dispatch_id=%s", dispatch_state.dispatch_id
            )
            return None

        if run.status != "completed":
            log.info("Workflow run %s still in status=%s", run.id, run.status)
            return None

        duration = (run.updated_at - run.created_at).total_seconds()
        status = CONCLUSION_TO_STATUS[run.conclusion]

        return [
            TestResult(
                status=status,
                duration=duration,
                run_url=run.html_url,
            )
        ]

    async def find_workflow_run(
        self, dispatch_id: str, dispatch_time: datetime
    ) -> WorkflowRun | None:
        """Find workflow run by dispatch ID in display_title.

        Uses the created filter to narrow search scope and paginates through
        all matching runs to ensure we don't miss the target run.
        """
        url = f"/repos/{self.config.owner}/{self.config.repo}/actions/runs"
        created_filter = f">={dispatch_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        page = 1

        while True:
            params = {"per_page": "100", "created": created_filter, "page": str(page)}

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    raise RuntimeError(
                        f"Failed to list workflow runs: {response.status} {text}"
                    )
                data = await response.json()

            runs_response = WorkflowRunsResponse.model_validate(data)

            for run in runs_response.workflow_runs:
                if dispatch_id in run.display_title:
                    return run

            if len(runs_response.workflow_runs) < 100:
                break

            page += 1

        return None

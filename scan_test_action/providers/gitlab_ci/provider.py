"""GitLab CI provider implementation."""

import json
import logging
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote

import aiohttp

from scan_test_action.models.definition import TestDefinition
from scan_test_action.models.result import TestResult
from scan_test_action.providers.base import PipelineProvider
from scan_test_action.providers.gitlab_ci.config import GitLabCIConfig
from scan_test_action.providers.gitlab_ci.models import Pipeline, PipelineStatus

log = logging.getLogger(__name__)

COMPLETED_STATUSES: frozenset[PipelineStatus] = frozenset(
    ["success", "failed", "canceled", "skipped", "manual"]
)

STATUS_TO_RESULT: Mapping[
    PipelineStatus, Literal["success", "failure", "timeout", "error"]
] = {
    "success": "success",
    "failed": "failure",
    "canceled": "error",
    "skipped": "error",
    "manual": "error",
}


@dataclass(frozen=True, kw_only=True)
class GitLabCIProvider(PipelineProvider[str]):
    """GitLab CI pipeline provider.

    Uses separate tokens for dispatch and polling:
    - trigger_token: Pipeline Trigger Token for POST /trigger/pipeline (no auth header)
    - api_token: Project Access Token for GET /pipelines/:id (Bearer token auth)

    Dispatch state is the pipeline ID string since GitLab returns it directly.
    """

    config: GitLabCIConfig
    session: aiohttp.ClientSession = field(repr=False)
    encoded_project_id: str = field(repr=False)

    @classmethod
    @asynccontextmanager
    async def from_config(
        cls, config: GitLabCIConfig
    ) -> AsyncGenerator["GitLabCIProvider", None]:
        """Create provider with managed session lifecycle."""
        async with aiohttp.ClientSession(
            base_url=config.api_base_url,
        ) as session:
            yield cls(
                config=config,
                session=session,
                encoded_project_id=quote(config.project_id, safe=""),
            )

    async def dispatch_scanner_tests(
        self,
        scanner_id: str,
        test_definition: TestDefinition,
        registry_ref: str,
        registry_repo: str,
    ) -> str:
        """Dispatch pipeline using Pipeline Trigger Token and return pipeline ID."""
        matrix_entries = [
            entry.model_dump(mode="json")
            for entry in test_definition.to_matrix_entries()
        ]

        url = f"projects/{self.encoded_project_id}/trigger/pipeline"
        payload = {
            "ref": self.config.ref,
            "token": self.config.trigger_token.get_secret_value(),
            "variables": {
                "SCANNER_ID": scanner_id,
                "REGISTRY_REF": registry_ref,
                "REGISTRY_REPO": registry_repo,
                "MATRIX_TESTS": json.dumps(matrix_entries),
            },
        }

        async with self.session.post(url, json=payload) as response:
            if response.status != 201:
                text = await response.text()
                raise RuntimeError(
                    f"Failed to create pipeline: {response.status} {text}"
                )
            data = await response.json()

        pipeline_id = data.get("id")
        if not isinstance(pipeline_id, int):
            raise RuntimeError("Pipeline ID not found in response")

        log.info("Created pipeline %s for scanner %s", pipeline_id, scanner_id)
        return str(pipeline_id)

    async def poll_status(self, dispatch_state: str) -> Sequence[TestResult] | None:
        """Check if pipeline is complete and return results."""
        pipeline = await self.get_pipeline(dispatch_state)

        if pipeline.status not in COMPLETED_STATUSES:
            log.info("Pipeline %s still in status=%s", pipeline.id, pipeline.status)
            return None

        duration = (pipeline.updated_at - pipeline.created_at).total_seconds()
        status = STATUS_TO_RESULT.get(pipeline.status, "error")

        return [
            TestResult(
                status=status,
                duration=duration,
                run_url=pipeline.web_url,
            )
        ]

    async def get_pipeline(self, pipeline_id: str) -> Pipeline:
        """Get pipeline by ID using the API token."""
        url = f"projects/{self.encoded_project_id}/pipelines/{pipeline_id}"
        headers = {
            "Authorization": f"Bearer {self.config.api_token.get_secret_value()}"
        }

        async with self.session.get(url, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"Failed to get pipeline: {response.status} {text}")
            data = await response.json()

        return Pipeline.model_validate(data)

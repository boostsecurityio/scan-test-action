"""Azure DevOps provider implementation."""

import base64
import json
import logging
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal

import aiohttp

from scan_test_action.models.definition import TestDefinition
from scan_test_action.models.result import TestResult
from scan_test_action.providers.azure_devops.config import AzureDevOpsConfig
from scan_test_action.providers.azure_devops.models import (
    PipelineRun,
    PipelineRunResult,
    PipelineRunState,
)
from scan_test_action.providers.base import PipelineProvider

log = logging.getLogger(__name__)

COMPLETED_STATES: frozenset[PipelineRunState] = frozenset(["completed", "canceling"])

RESULT_TO_STATUS: Mapping[
    PipelineRunResult | None, Literal["success", "failure", "timeout", "error"]
] = {
    "succeeded": "success",
    "failed": "failure",
    "canceled": "error",
}


@dataclass(frozen=True, kw_only=True)
class AzureDevOpsProvider(PipelineProvider[str]):
    """Azure DevOps pipeline provider.

    Dispatch state is the run ID string since Azure returns it directly.
    """

    config: AzureDevOpsConfig
    session: aiohttp.ClientSession = field(repr=False)

    @classmethod
    @asynccontextmanager
    async def from_config(
        cls, config: AzureDevOpsConfig
    ) -> AsyncGenerator["AzureDevOpsProvider", None]:
        """Create provider with managed session lifecycle."""
        # Azure DevOps uses Basic Auth with empty username and PAT as password
        auth_string = f":{config.token.get_secret_value()}"
        auth_bytes = base64.b64encode(auth_string.encode("ascii")).decode("ascii")
        headers = {
            "Authorization": f"Basic {auth_bytes}",
            "Content-Type": "application/json",
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
    ) -> str:
        """Dispatch pipeline run and return run ID for polling."""
        matrix_entries = [
            {"test_name": test.name, "scan_path": path}
            for test in test_definition.tests
            for path in test.scan_paths
        ]

        template_params = {
            "SCANNER_ID": scanner_id,
            "REGISTRY_REF": registry_ref,
            "REGISTRY_REPO": registry_repo,
            "MATRIX_TESTS": json.dumps(matrix_entries),
        }

        url = (
            f"/{self.config.organization}/{self.config.project}"
            f"/_apis/pipelines/{self.config.pipeline_id}/runs?api-version=7.1"
        )
        payload = {"templateParameters": template_params}

        async with self.session.post(url, json=payload) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"Failed to run pipeline: {response.status} {text}")
            data = await response.json()

        run_id = data.get("id")
        if not isinstance(run_id, int):
            raise RuntimeError("Run ID not found in response")

        log.info("Created pipeline run %s for scanner %s", run_id, scanner_id)
        return str(run_id)

    async def poll_status(self, dispatch_state: str) -> Sequence[TestResult] | None:
        """Check if pipeline run is complete and return results."""
        run = await self.get_run(dispatch_state)

        if run.state not in COMPLETED_STATES:
            log.info("Pipeline run %s still in state=%s", run.id, run.state)
            return None

        duration = 0.0
        if run.finished_date is not None:
            duration = (run.finished_date - run.created_date).total_seconds()

        status = RESULT_TO_STATUS.get(run.result, "error")
        run_url = run.links.web.href if run.links and run.links.web else ""

        return [
            TestResult(
                status=status,
                duration=duration,
                run_url=run_url,
            )
        ]

    async def get_run(self, run_id: str) -> PipelineRun:
        """Get pipeline run by ID."""
        url = (
            f"/{self.config.organization}/{self.config.project}"
            f"/_apis/pipelines/{self.config.pipeline_id}/runs/{run_id}"
            "?api-version=7.1"
        )

        async with self.session.get(url) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(
                    f"Failed to get pipeline run: {response.status} {text}"
                )
            data = await response.json()

        return PipelineRun.model_validate(data)

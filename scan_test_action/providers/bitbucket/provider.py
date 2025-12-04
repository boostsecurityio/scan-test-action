"""Bitbucket Pipelines provider implementation."""

import json
import logging
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal

import aiohttp

from scan_test_action.models.definition import TestDefinition
from scan_test_action.models.result import TestResult
from scan_test_action.providers.base import PipelineProvider
from scan_test_action.providers.bitbucket.config import BitbucketConfig
from scan_test_action.providers.bitbucket.models import (
    Pipeline,
    PipelineCreateResponse,
)

log = logging.getLogger(__name__)

# Bitbucket API state values are poorly documented. These are the known terminal states.
COMPLETED_STATES: frozenset[str] = frozenset(
    ["COMPLETED", "STOPPED", "ERROR", "FAILED"]
)

RESULT_TO_STATUS: Mapping[
    str | None, Literal["success", "failure", "timeout", "error"]
] = {
    "SUCCESSFUL": "success",
    "FAILED": "failure",
    "ERROR": "error",
    "STOPPED": "error",
    None: "error",
}


@dataclass(frozen=True, kw_only=True)
class DispatchState:
    """State returned from dispatch for polling."""

    pipeline_uuid: str  # UUID with braces like {abc-123-def}
    run_url: str


@dataclass(frozen=True, kw_only=True)
class BitbucketProvider(PipelineProvider[DispatchState]):
    """Bitbucket Pipelines provider.

    Uses OAuth Bearer token authentication.
    """

    config: BitbucketConfig
    session: aiohttp.ClientSession = field(repr=False)

    @classmethod
    @asynccontextmanager
    async def from_config(
        cls, config: BitbucketConfig
    ) -> AsyncGenerator["BitbucketProvider", None]:
        """Create provider with managed session lifecycle."""
        headers = {
            "Authorization": f"Bearer {config.token.get_secret_value()}",
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
    ) -> DispatchState:
        """Dispatch pipeline and return state for polling."""
        matrix_entries = [
            entry.model_dump(mode="json")
            for entry in test_definition.to_matrix_entries()
        ]

        variables = [
            {"key": "SCANNER_ID", "value": scanner_id},
            {"key": "REGISTRY_REF", "value": registry_ref},
            {"key": "REGISTRY_REPO", "value": registry_repo},
            {"key": "MATRIX_TESTS", "value": json.dumps(matrix_entries)},
        ]

        url = f"repositories/{self.config.workspace}/{self.config.repo_slug}/pipelines/"
        payload = {
            "target": {
                "type": "pipeline_ref_target",
                "selector": {
                    "type": "custom",
                    "pattern": "test-scanner",
                },
                "ref_name": self.config.branch,
                "ref_type": "branch",
            },
            "variables": variables,
        }

        async with self.session.post(url, json=payload) as response:
            if response.status != 201:
                text = await response.text()
                raise RuntimeError(
                    f"Failed to trigger pipeline: {response.status} {text}"
                )
            data = await response.json()
            run_url = response.headers.get("Location", "")

        create_response = PipelineCreateResponse.model_validate(data)

        log.info("Created pipeline %s for scanner %s", create_response.uuid, scanner_id)
        return DispatchState(
            pipeline_uuid=create_response.uuid,
            run_url=run_url,
        )

    async def poll_status(
        self, dispatch_state: DispatchState
    ) -> Sequence[TestResult] | None:
        """Check if pipeline is complete and return results."""
        pipeline = await self.get_pipeline(dispatch_state.pipeline_uuid)

        if pipeline.state.name not in COMPLETED_STATES:
            log.info(
                "Pipeline %s still in state=%s",
                dispatch_state.pipeline_uuid,
                pipeline.state.name,
            )
            return None

        duration = 0.0
        if pipeline.completed_on is not None:
            duration = (pipeline.completed_on - pipeline.created_on).total_seconds()

        result_name = pipeline.state.result.name if pipeline.state.result else None
        status = RESULT_TO_STATUS.get(result_name, "error")

        return [
            TestResult(
                status=status,
                duration=duration,
                run_url=dispatch_state.run_url,
            )
        ]

    async def get_pipeline(self, pipeline_uuid: str) -> Pipeline:
        """Get pipeline by UUID."""
        url = (
            f"repositories/{self.config.workspace}/"
            f"{self.config.repo_slug}/pipelines/{pipeline_uuid}"
        )

        async with self.session.get(url) as response:
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(f"Failed to get pipeline: {response.status} {text}")
            data = await response.json()

        return Pipeline.model_validate(data)

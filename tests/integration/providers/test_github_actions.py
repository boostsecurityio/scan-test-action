"""Integration tests for GitHub Actions provider."""

import re
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

import pytest
from aioresponses import aioresponses as aioresponses_cls
from pydantic import SecretStr
from yarl import URL

from scan_test_action.providers.github_actions import (
    GitHubActionsConfig,
    GitHubActionsProvider,
)
from scan_test_action.providers.github_actions.provider import DispatchState
from scan_test_action.testing.github.factories import (
    TestDefinitionFactory,
    TestFactory,
    TestSourceFactory,
)
from scan_test_action.testing.github.payloads import (
    workflow_run,
    workflow_runs_response,
)

API_BASE_URL = "http://github.test"


@pytest.fixture
def config() -> GitHubActionsConfig:
    """Create test configuration."""
    return GitHubActionsConfig(
        token=SecretStr("test-token"),
        owner="test-owner",
        repo="test-repo",
        workflow_id="test.yml",
        api_base_url=API_BASE_URL,
    )


@pytest.fixture
async def provider(
    config: GitHubActionsConfig, aioresponses: aioresponses_cls
) -> AsyncGenerator[GitHubActionsProvider, None]:
    """Create provider with managed session."""
    async with GitHubActionsProvider.from_config(config) as impl:
        yield impl


class TestDispatchScannerTests:
    """Tests for dispatch_scanner_tests."""

    async def test_dispatches_workflow_with_correct_payload(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Dispatches workflow with correct API parameters."""
        dispatch_url = (
            f"{API_BASE_URL}/repos/test-owner/test-repo"
            "/actions/workflows/test.yml/dispatches"
        )
        aioresponses.post(dispatch_url, status=204)

        test_definition = TestDefinitionFactory.build(
            tests=[
                TestFactory.build(
                    name="smoke test",
                    source=TestSourceFactory.build(),
                    scan_paths=["."],
                )
            ]
        )

        state = await provider.dispatch_scanner_tests(
            scanner_id="org/scanner",
            test_definition=test_definition,
            registry_ref="abc123",
            registry_repo="org/registry",
        )

        aioresponses.assert_called_once()  # type: ignore[no-untyped-call]
        call = aioresponses.requests[("POST", URL(dispatch_url))][0]
        payload = call.kwargs["json"]
        assert payload["ref"] == "main"
        assert payload["inputs"]["scanner_id"] == "org/scanner"
        assert payload["inputs"]["registry_ref"] == "abc123"
        assert payload["inputs"]["registry_repo"] == "org/registry"
        assert state.dispatch_id in payload["inputs"]["dispatch_id"]

    async def test_dispatches_with_multiple_tests_and_paths(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Dispatches workflow with multiple tests and scan paths in matrix."""
        dispatch_url = (
            f"{API_BASE_URL}/repos/test-owner/test-repo"
            "/actions/workflows/test.yml/dispatches"
        )
        aioresponses.post(dispatch_url, status=204)

        test_definition = TestDefinitionFactory.build(
            tests=[
                TestFactory.build(
                    name="source scan",
                    type="source-code",
                    source=TestSourceFactory.build(
                        url="https://github.com/org/repo1.git",
                        ref="main",
                    ),
                    scan_paths=["src", "lib"],
                ),
                TestFactory.build(
                    name="container scan",
                    type="container-image",
                    source=TestSourceFactory.build(
                        url="https://github.com/org/repo2.git",
                        ref="v1.0.0",
                    ),
                    scan_paths=["."],
                ),
            ]
        )

        await provider.dispatch_scanner_tests(
            scanner_id="org/scanner",
            test_definition=test_definition,
            registry_ref="abc123",
            registry_repo="org/registry",
        )

        call = aioresponses.requests[("POST", URL(dispatch_url))][0]
        payload = call.kwargs["json"]
        import json

        matrix = json.loads(payload["inputs"]["matrix"])
        assert len(matrix) == 3
        assert matrix[0] == {"test_name": "source scan", "scan_path": "src"}
        assert matrix[1] == {"test_name": "source scan", "scan_path": "lib"}
        assert matrix[2] == {"test_name": "container scan", "scan_path": "."}

    async def test_generates_unique_dispatch_ids(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Each dispatch generates a unique ID."""
        dispatch_url = (
            f"{API_BASE_URL}/repos/test-owner/test-repo"
            "/actions/workflows/test.yml/dispatches"
        )
        aioresponses.post(dispatch_url, status=204)
        aioresponses.post(dispatch_url, status=204)

        test_definition = TestDefinitionFactory.build(
            tests=[TestFactory.build(source=TestSourceFactory.build())]
        )

        state1 = await provider.dispatch_scanner_tests(
            scanner_id="org/scanner",
            test_definition=test_definition,
            registry_ref="abc123",
            registry_repo="org/registry",
        )
        state2 = await provider.dispatch_scanner_tests(
            scanner_id="org/scanner",
            test_definition=test_definition,
            registry_ref="abc123",
            registry_repo="org/registry",
        )

        assert state1.dispatch_id != state2.dispatch_id
        assert state1.dispatch_time.tzinfo == timezone.utc
        assert state2.dispatch_time.tzinfo == timezone.utc

    async def test_raises_on_dispatch_failure(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError when dispatch fails."""
        aioresponses.post(
            f"{API_BASE_URL}/repos/test-owner/test-repo"
            "/actions/workflows/test.yml/dispatches",
            status=400,
            body="Bad Request",
        )

        test_definition = TestDefinitionFactory.build(
            tests=[TestFactory.build(source=TestSourceFactory.build())]
        )

        with pytest.raises(RuntimeError, match="Failed to dispatch workflow: 400"):
            await provider.dispatch_scanner_tests(
                scanner_id="org/scanner",
                test_definition=test_definition,
                registry_ref="abc123",
                registry_repo="org/registry",
            )


class TestPollStatus:
    """Tests for poll_status."""

    async def test_returns_none_when_run_not_found(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns None when workflow run not found."""
        aioresponses.get(
            re.compile(rf"{API_BASE_URL}/repos/test-owner/test-repo/actions/runs.*"),
            payload=workflow_runs_response(),
        )

        state = DispatchState(
            dispatch_id="not-found-id",
            dispatch_time=datetime.now(timezone.utc),
        )
        result = await provider.poll_status(state)

        assert result is None

    async def test_returns_none_when_run_in_progress(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns None when workflow is still running."""
        dispatch_id = "test-dispatch-id"
        aioresponses.get(
            re.compile(rf"{API_BASE_URL}/repos/test-owner/test-repo/actions/runs.*"),
            payload=workflow_runs_response(
                workflow_runs=[
                    workflow_run(
                        status="in_progress",
                        conclusion=None,
                        display_title=f"[{dispatch_id}]",
                    )
                ]
            ),
        )

        state = DispatchState(
            dispatch_id=dispatch_id,
            dispatch_time=datetime.now(timezone.utc),
        )
        result = await provider.poll_status(state)

        assert result is None

    async def test_returns_results_with_correct_params(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Polls with correct created filter and returns results."""
        dispatch_id = "test-dispatch-id"
        dispatch_time = datetime(2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        aioresponses.get(
            re.compile(rf"{API_BASE_URL}/repos/test-owner/test-repo/actions/runs.*"),
            payload=workflow_runs_response(
                workflow_runs=[
                    workflow_run(
                        run_id=123,
                        display_title=f"[{dispatch_id}]",
                        html_url="https://github.com/test/runs/123",
                        created_at="2099-01-01T12:00:00Z",
                        updated_at="2099-01-01T12:01:30Z",
                    )
                ]
            ),
        )

        state = DispatchState(dispatch_id=dispatch_id, dispatch_time=dispatch_time)
        results = await provider.poll_status(state)

        aioresponses.assert_called_once()  # type: ignore[no-untyped-call]
        call_url = str(next(iter(aioresponses.requests.keys()))[1])
        assert "created=" in call_url
        assert "per_page=100" in call_url

        assert results is not None
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].duration == 90.0
        assert results[0].run_url == "https://github.com/test/runs/123"

    @pytest.mark.parametrize(
        ("conclusion", "expected_status"),
        [
            ("success", "success"),
            ("failure", "failure"),
            ("cancelled", "error"),
            ("timed_out", "timeout"),
            ("action_required", "error"),
            ("neutral", "success"),
            ("skipped", "error"),
            ("stale", "error"),
        ],
    )
    async def test_maps_conclusion_to_status(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
        conclusion: str,
        expected_status: str,
    ) -> None:
        """Maps GitHub conclusion to test status."""
        dispatch_id = "test-dispatch-id"
        aioresponses.get(
            re.compile(rf"{API_BASE_URL}/repos/test-owner/test-repo/actions/runs.*"),
            payload=workflow_runs_response(
                workflow_runs=[
                    workflow_run(
                        conclusion=conclusion,
                        display_title=f"[{dispatch_id}]",
                    )
                ]
            ),
        )

        state = DispatchState(
            dispatch_id=dispatch_id,
            dispatch_time=datetime.now(timezone.utc),
        )
        results = await provider.poll_status(state)

        assert results is not None
        assert results[0].status == expected_status

    async def test_raises_on_api_error(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError on API failure."""
        aioresponses.get(
            re.compile(rf"{API_BASE_URL}/repos/test-owner/test-repo/actions/runs.*"),
            status=500,
            body="Internal Server Error",
        )

        state = DispatchState(
            dispatch_id="test-id",
            dispatch_time=datetime.now(timezone.utc),
        )

        with pytest.raises(RuntimeError, match="Failed to list workflow runs: 500"):
            await provider.poll_status(state)


class TestFindWorkflowRun:
    """Tests for find_workflow_run with pagination."""

    async def test_paginates_through_all_pages(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Paginates through multiple pages to find run."""
        dispatch_id = "target-dispatch-id"
        dispatch_time = datetime(2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # First page - 100 runs, target not found
        aioresponses.get(
            re.compile(rf"{API_BASE_URL}/repos/test-owner/test-repo/actions/runs.*"),
            payload=workflow_runs_response(
                workflow_runs=[
                    workflow_run(run_id=i, display_title=f"[other-id-{i}]")
                    for i in range(100)
                ]
            ),
        )

        # Second page - target found
        aioresponses.get(
            re.compile(rf"{API_BASE_URL}/repos/test-owner/test-repo/actions/runs.*"),
            payload=workflow_runs_response(
                workflow_runs=[
                    workflow_run(run_id=999, display_title=f"[{dispatch_id}]")
                ]
            ),
        )

        run = await provider.find_workflow_run(dispatch_id, dispatch_time)

        assert run is not None
        assert run.id == 999

    async def test_returns_none_when_not_found_after_pagination(
        self,
        provider: GitHubActionsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns None when run not found in any page."""
        dispatch_time = datetime(2099, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        aioresponses.get(
            re.compile(rf"{API_BASE_URL}/repos/test-owner/test-repo/actions/runs.*"),
            payload=workflow_runs_response(
                workflow_runs=[workflow_run(run_id=1, display_title="[other-id]")]
            ),
        )

        run = await provider.find_workflow_run("not-found-id", dispatch_time)

        assert run is None

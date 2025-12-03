"""Integration tests for Azure DevOps provider."""

from collections.abc import AsyncGenerator

import pytest
from aioresponses import aioresponses as aioresponses_cls
from pydantic import SecretStr
from yarl import URL

from scan_test_action.providers.azure_devops import (
    AzureDevOpsConfig,
    AzureDevOpsProvider,
)
from scan_test_action.testing.azure.payloads import create_run_response, pipeline_run
from scan_test_action.testing.github.factories import (
    TestDefinitionFactory,
    TestFactory,
    TestSourceFactory,
)

API_BASE_URL = "http://azure.test"


@pytest.fixture
def config() -> AzureDevOpsConfig:
    """Create test configuration."""
    return AzureDevOpsConfig(
        token=SecretStr("test-pat-token"),
        organization="test-org",
        project="test-project",
        pipeline_id=42,
        api_base_url=API_BASE_URL,
    )


@pytest.fixture
async def provider(
    config: AzureDevOpsConfig, aioresponses: aioresponses_cls
) -> AsyncGenerator[AzureDevOpsProvider, None]:
    """Create provider with managed session."""
    async with AzureDevOpsProvider.from_config(config) as impl:
        yield impl


class TestDispatchScannerTests:
    """Tests for dispatch_scanner_tests."""

    async def test_dispatches_pipeline_with_correct_payload(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Dispatches pipeline with correct API parameters."""
        dispatch_url = (
            f"{API_BASE_URL}/test-org/test-project"
            "/_apis/pipelines/42/runs?api-version=7.1"
        )
        aioresponses.post(
            dispatch_url,
            status=200,
            payload=create_run_response(run_id=999),
        )

        test_definition = TestDefinitionFactory.build(
            tests=[
                TestFactory.build(
                    name="smoke test",
                    source=TestSourceFactory.build(),
                    scan_paths=["."],
                )
            ]
        )

        run_id = await provider.dispatch_scanner_tests(
            scanner_id="org/scanner",
            test_definition=test_definition,
            registry_ref="abc123",
            registry_repo="org/registry",
        )

        assert run_id == "999"

        aioresponses.assert_called_once()  # type: ignore[no-untyped-call]
        call = aioresponses.requests[("POST", URL(dispatch_url))][0]
        payload = call.kwargs["json"]
        assert "templateParameters" in payload
        params = payload["templateParameters"]
        assert params["SCANNER_ID"] == "org/scanner"
        assert params["REGISTRY_REF"] == "abc123"
        assert params["REGISTRY_REPO"] == "org/registry"

    async def test_dispatches_with_multiple_tests_and_paths(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Dispatches pipeline with multiple tests and scan paths in matrix."""
        dispatch_url = (
            f"{API_BASE_URL}/test-org/test-project"
            "/_apis/pipelines/42/runs?api-version=7.1"
        )
        aioresponses.post(
            dispatch_url,
            status=200,
            payload=create_run_response(run_id=999),
        )

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
                    timeout="5m",
                ),
                TestFactory.build(
                    name="container scan",
                    type="container-image",
                    source=TestSourceFactory.build(
                        url="https://github.com/org/repo2.git",
                        ref="v1.0.0",
                    ),
                    scan_paths=["."],
                    timeout="5m",
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

        matrix = json.loads(payload["templateParameters"]["MATRIX_TESTS"])
        assert len(matrix) == 3
        assert matrix[0] == {
            "test_name": "source scan",
            "test_type": "source-code",
            "source_url": "https://github.com/org/repo1.git",
            "source_ref": "main",
            "scan_path": "src",
            "timeout": "5m",
        }
        assert matrix[1] == {
            "test_name": "source scan",
            "test_type": "source-code",
            "source_url": "https://github.com/org/repo1.git",
            "source_ref": "main",
            "scan_path": "lib",
            "timeout": "5m",
        }
        assert matrix[2] == {
            "test_name": "container scan",
            "test_type": "container-image",
            "source_url": "https://github.com/org/repo2.git",
            "source_ref": "v1.0.0",
            "scan_path": ".",
            "timeout": "5m",
        }

    async def test_raises_on_dispatch_failure(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError when dispatch fails."""
        aioresponses.post(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs?api-version=7.1",
            status=400,
            body="Bad Request",
        )

        test_definition = TestDefinitionFactory.build(
            tests=[TestFactory.build(source=TestSourceFactory.build())]
        )

        with pytest.raises(RuntimeError, match="Failed to run pipeline: 400"):
            await provider.dispatch_scanner_tests(
                scanner_id="org/scanner",
                test_definition=test_definition,
                registry_ref="abc123",
                registry_repo="org/registry",
            )

    async def test_raises_on_missing_run_id(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError when run ID is missing from response."""
        aioresponses.post(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs?api-version=7.1",
            status=200,
            payload={"name": "test", "_links": {}},
        )

        test_definition = TestDefinitionFactory.build(
            tests=[TestFactory.build(source=TestSourceFactory.build())]
        )

        with pytest.raises(RuntimeError, match="Run ID not found"):
            await provider.dispatch_scanner_tests(
                scanner_id="org/scanner",
                test_definition=test_definition,
                registry_ref="abc123",
                registry_repo="org/registry",
            )


class TestPollStatus:
    """Tests for poll_status."""

    async def test_returns_none_when_run_in_progress(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns None when pipeline run is still in progress."""
        aioresponses.get(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs/999?api-version=7.1",
            payload=pipeline_run(state="inProgress", result=None, finished_date=None),
        )

        result = await provider.poll_status("999")

        assert result is None

    async def test_returns_results_on_success(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns results when pipeline run completes successfully."""
        aioresponses.get(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs/999?api-version=7.1",
            payload=pipeline_run(
                run_id=999,
                state="completed",
                result="succeeded",
                web_url="https://dev.azure.com/test/results/999",
                created_date="2099-01-01T12:00:00Z",
                finished_date="2099-01-01T12:01:30Z",
            ),
        )

        results = await provider.poll_status("999")

        assert results is not None
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].duration == 90.0
        assert results[0].run_url == "https://dev.azure.com/test/results/999"

    @pytest.mark.parametrize(
        ("azure_result", "expected_status"),
        [
            ("succeeded", "success"),
            ("failed", "failure"),
            ("canceled", "error"),
        ],
    )
    async def test_maps_result_correctly(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
        azure_result: str,
        expected_status: str,
    ) -> None:
        """Maps Azure pipeline result to test result status."""
        aioresponses.get(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs/999?api-version=7.1",
            payload=pipeline_run(state="completed", result=azure_result),
        )

        results = await provider.poll_status("999")

        assert results is not None
        assert results[0].status == expected_status

    async def test_raises_on_api_error(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError on API failure."""
        aioresponses.get(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs/999?api-version=7.1",
            status=404,
            body="Not Found",
        )

        with pytest.raises(RuntimeError, match="Failed to get pipeline run: 404"):
            await provider.poll_status("999")

    async def test_handles_missing_links(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Handles missing _links gracefully."""
        payload = pipeline_run(state="completed", result="succeeded")
        del payload["_links"]

        aioresponses.get(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs/999?api-version=7.1",
            payload=payload,
        )

        results = await provider.poll_status("999")

        assert results is not None
        assert results[0].run_url == ""

    async def test_handles_missing_finished_date(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Handles missing finishedDate with zero duration."""
        aioresponses.get(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs/999?api-version=7.1",
            payload=pipeline_run(
                state="completed",
                result="succeeded",
                finished_date=None,
            ),
        )

        results = await provider.poll_status("999")

        assert results is not None
        assert results[0].duration == 0.0


class TestGetRun:
    """Tests for get_run."""

    async def test_returns_pipeline_run(
        self,
        provider: AzureDevOpsProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns pipeline run model from API response."""
        aioresponses.get(
            f"{API_BASE_URL}/test-org/test-project/_apis/pipelines/42/runs/999?api-version=7.1",
            payload=pipeline_run(run_id=999, name="Test Run", state="completed"),
        )

        result = await provider.get_run("999")

        assert result.id == 999
        assert result.name == "Test Run"
        assert result.state == "completed"

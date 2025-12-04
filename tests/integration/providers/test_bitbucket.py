"""Integration tests for Bitbucket Pipelines provider."""

from collections.abc import AsyncGenerator

import pytest
from aioresponses import aioresponses as aioresponses_cls
from pydantic import SecretStr
from yarl import URL

from scan_test_action.providers.bitbucket import BitbucketConfig, BitbucketProvider
from scan_test_action.testing.bitbucket.payloads import (
    create_pipeline_response,
    pipeline,
)
from scan_test_action.testing.github.factories import (
    TestDefinitionFactory,
    TestFactory,
    TestSourceFactory,
)

API_BASE_URL = "http://bitbucket.test/2.0/"


@pytest.fixture
def config() -> BitbucketConfig:
    """Create test configuration."""
    return BitbucketConfig(
        token=SecretStr("test-oauth-token"),
        workspace="test-workspace",
        repo_slug="test-repo",
        api_base_url=API_BASE_URL,
    )


@pytest.fixture
async def provider(
    config: BitbucketConfig, aioresponses: aioresponses_cls
) -> AsyncGenerator[BitbucketProvider, None]:
    """Create provider with managed session."""
    async with BitbucketProvider.from_config(config) as impl:
        yield impl


class TestDispatchScannerTests:
    """Tests for dispatch_scanner_tests."""

    async def test_dispatches_pipeline_with_correct_payload(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Dispatches pipeline with correct API parameters."""
        dispatch_url = f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/"
        aioresponses.post(
            dispatch_url,
            status=201,
            payload=create_pipeline_response(uuid="{abc-123-def}", build_number=42),
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

        dispatch_state = await provider.dispatch_scanner_tests(
            scanner_id="org/scanner",
            test_definition=test_definition,
            registry_ref="abc123",
            registry_repo="org/registry",
        )

        assert dispatch_state.pipeline_uuid == "{abc-123-def}"
        assert (
            dispatch_state.run_url
            == "https://bitbucket.org/test-workspace/test-repo/pipelines/results/42"
        )

        aioresponses.assert_called_once()  # type: ignore[no-untyped-call]
        call = aioresponses.requests[("POST", URL(dispatch_url))][0]
        payload = call.kwargs["json"]
        assert payload["target"]["type"] == "pipeline_ref_target"
        assert payload["target"]["ref_name"] == "main"
        assert payload["target"]["selector"]["pattern"] == "test-scanner"

        variables = {v["key"]: v["value"] for v in payload["variables"]}
        assert variables["SCANNER_ID"] == "org/scanner"
        assert variables["REGISTRY_REF"] == "abc123"
        assert variables["REGISTRY_REPO"] == "org/registry"

    async def test_dispatches_with_multiple_tests_and_paths(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Dispatches pipeline with multiple tests and scan paths in matrix."""
        dispatch_url = f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/"
        aioresponses.post(
            dispatch_url,
            status=201,
            payload=create_pipeline_response(uuid="{abc-123-def}", build_number=42),
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
        variables = {v["key"]: v["value"] for v in payload["variables"]}
        import json

        matrix = json.loads(variables["MATRIX_TESTS"])
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
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError when dispatch fails."""
        aioresponses.post(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/",
            status=400,
            body="Bad Request",
        )

        test_definition = TestDefinitionFactory.build(
            tests=[TestFactory.build(source=TestSourceFactory.build())]
        )

        with pytest.raises(RuntimeError, match="Failed to trigger pipeline: 400"):
            await provider.dispatch_scanner_tests(
                scanner_id="org/scanner",
                test_definition=test_definition,
                registry_ref="abc123",
                registry_repo="org/registry",
            )


class TestPollStatus:
    """Tests for poll_status."""

    async def test_returns_none_when_pipeline_pending(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns None when pipeline is pending."""
        from scan_test_action.providers.bitbucket.provider import DispatchState

        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            payload=pipeline(state_name="PENDING", result_name=None, completed_on=None),
        )

        dispatch_state = DispatchState(
            pipeline_uuid="{abc-123-def}",
            run_url="https://bitbucket.org/test-workspace/test-repo/pipelines/results/42",
        )
        result = await provider.poll_status(dispatch_state)

        assert result is None

    async def test_returns_none_when_pipeline_in_progress(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns None when pipeline is in progress."""
        from scan_test_action.providers.bitbucket.provider import DispatchState

        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            payload=pipeline(
                state_name="IN_PROGRESS", result_name=None, completed_on=None
            ),
        )

        dispatch_state = DispatchState(
            pipeline_uuid="{abc-123-def}",
            run_url="https://bitbucket.org/test-workspace/test-repo/pipelines/results/42",
        )
        result = await provider.poll_status(dispatch_state)

        assert result is None

    async def test_returns_results_on_success(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns results when pipeline completes successfully."""
        from scan_test_action.providers.bitbucket.provider import DispatchState

        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            payload=pipeline(
                uuid="{abc-123-def}",
                build_number=42,
                state_name="COMPLETED",
                result_name="SUCCESSFUL",
                created_on="2099-01-01T12:00:00.000000+00:00",
                completed_on="2099-01-01T12:01:30.000000+00:00",
            ),
        )

        dispatch_state = DispatchState(
            pipeline_uuid="{abc-123-def}",
            run_url="https://bitbucket.org/test-workspace/test-repo/pipelines/results/42",
        )
        results = await provider.poll_status(dispatch_state)

        assert results is not None
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].duration == 90.0
        assert (
            results[0].run_url
            == "https://bitbucket.org/test-workspace/test-repo/pipelines/results/42"
        )

    @pytest.mark.parametrize(
        ("result_name", "expected_status"),
        [
            ("SUCCESSFUL", "success"),
            ("FAILED", "failure"),
            ("ERROR", "error"),
            ("STOPPED", "error"),
        ],
    )
    async def test_maps_result_correctly(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
        result_name: str,
        expected_status: str,
    ) -> None:
        """Maps Bitbucket pipeline result to test result status."""
        from scan_test_action.providers.bitbucket.provider import DispatchState

        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            payload=pipeline(state_name="COMPLETED", result_name=result_name),
        )

        dispatch_state = DispatchState(
            pipeline_uuid="{abc-123-def}",
            run_url="https://bitbucket.org/test-workspace/test-repo/pipelines/results/42",
        )
        results = await provider.poll_status(dispatch_state)

        assert results is not None
        assert results[0].status == expected_status

    async def test_handles_unknown_result_as_error(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Treats unknown result values as error."""
        from scan_test_action.providers.bitbucket.provider import DispatchState

        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            payload=pipeline(state_name="COMPLETED", result_name="UNKNOWN_RESULT"),
        )

        dispatch_state = DispatchState(
            pipeline_uuid="{abc-123-def}",
            run_url="https://bitbucket.org/test-workspace/test-repo/pipelines/results/42",
        )
        results = await provider.poll_status(dispatch_state)

        assert results is not None
        assert results[0].status == "error"

    @pytest.mark.parametrize(
        "state_name",
        ["STOPPED", "ERROR", "FAILED"],
    )
    async def test_handles_completed_states_without_result(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
        state_name: str,
    ) -> None:
        """Handles completed states that may not have a result."""
        from scan_test_action.providers.bitbucket.provider import DispatchState

        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            payload=pipeline(state_name=state_name, result_name=None),
        )

        dispatch_state = DispatchState(
            pipeline_uuid="{abc-123-def}",
            run_url="https://bitbucket.org/test-workspace/test-repo/pipelines/results/42",
        )
        results = await provider.poll_status(dispatch_state)

        assert results is not None
        assert results[0].status == "error"

    async def test_raises_on_api_error(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError on API failure."""
        from scan_test_action.providers.bitbucket.provider import DispatchState

        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            status=404,
            body="Not Found",
        )

        dispatch_state = DispatchState(
            pipeline_uuid="{abc-123-def}",
            run_url="https://bitbucket.org/test-workspace/test-repo/pipelines/results/42",
        )

        with pytest.raises(RuntimeError, match="Failed to get pipeline: 404"):
            await provider.poll_status(dispatch_state)

    async def test_handles_missing_completed_on(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Handles missing completed_on with zero duration."""
        from scan_test_action.providers.bitbucket.provider import DispatchState

        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            payload=pipeline(
                state_name="COMPLETED",
                result_name="SUCCESSFUL",
                completed_on=None,
            ),
        )

        dispatch_state = DispatchState(
            pipeline_uuid="{abc-123-def}",
            run_url="https://bitbucket.org/test-workspace/test-repo/pipelines/results/42",
        )
        results = await provider.poll_status(dispatch_state)

        assert results is not None
        assert results[0].duration == 0.0


class TestGetPipeline:
    """Tests for get_pipeline."""

    async def test_returns_pipeline(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns pipeline model from API response."""
        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            payload=pipeline(
                uuid="{abc-123-def}",
                build_number=42,
                state_name="COMPLETED",
                result_name="SUCCESSFUL",
            ),
        )

        result = await provider.get_pipeline("{abc-123-def}")

        assert result.uuid == "{abc-123-def}"
        assert result.build_number == 42
        assert result.state.name == "COMPLETED"
        assert result.state.result is not None
        assert result.state.result.name == "SUCCESSFUL"

    async def test_raises_on_api_error(
        self,
        provider: BitbucketProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError on API failure."""
        aioresponses.get(
            f"{API_BASE_URL}repositories/test-workspace/test-repo/pipelines/%7Babc-123-def%7D",
            status=500,
            body="Internal Server Error",
        )

        with pytest.raises(RuntimeError, match="Failed to get pipeline: 500"):
            await provider.get_pipeline("{abc-123-def}")

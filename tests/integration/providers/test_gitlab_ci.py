"""Integration tests for GitLab CI provider."""

from collections.abc import AsyncGenerator

import pytest
from aioresponses import aioresponses as aioresponses_cls
from pydantic import SecretStr
from yarl import URL

from scan_test_action.providers.gitlab_ci import GitLabCIConfig, GitLabCIProvider
from scan_test_action.testing.github.factories import (
    TestDefinitionFactory,
    TestFactory,
    TestSourceFactory,
)
from scan_test_action.testing.gitlab.payloads import (
    create_pipeline_response,
    pipeline,
)

API_BASE_URL = "http://gitlab.test/api/v4/"


@pytest.fixture
def config() -> GitLabCIConfig:
    """Create test configuration."""
    return GitLabCIConfig(
        trigger_token=SecretStr("glptt-trigger-token-123"),
        api_token=SecretStr("glpat-api-token-456"),
        project_id="12345",
        api_base_url=API_BASE_URL,
    )


@pytest.fixture
async def provider(
    config: GitLabCIConfig, aioresponses: aioresponses_cls
) -> AsyncGenerator[GitLabCIProvider, None]:
    """Create provider with managed session."""
    async with GitLabCIProvider.from_config(config) as impl:
        yield impl


class TestDispatchScannerTests:
    """Tests for dispatch_scanner_tests."""

    async def test_dispatches_pipeline_with_correct_payload(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Dispatches pipeline via trigger endpoint with correct API parameters."""
        dispatch_url = f"{API_BASE_URL}projects/12345/trigger/pipeline"
        aioresponses.post(
            dispatch_url,
            status=201,
            payload=create_pipeline_response(pipeline_id=789),
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

        pipeline_id = await provider.dispatch_scanner_tests(
            scanner_id="org/scanner",
            test_definition=test_definition,
            registry_ref="abc123",
            registry_repo="org/registry",
        )

        assert pipeline_id == "789"

        aioresponses.assert_called_once()  # type: ignore[no-untyped-call]
        call = aioresponses.requests[("POST", URL(dispatch_url))][0]
        payload = call.kwargs["json"]
        assert payload["ref"] == "main"
        assert payload["token"] == "glptt-trigger-token-123"
        assert payload["variables"]["SCANNER_ID"] == "org/scanner"
        assert payload["variables"]["REGISTRY_REF"] == "abc123"
        assert payload["variables"]["REGISTRY_REPO"] == "org/registry"

    async def test_dispatches_with_multiple_tests_and_paths(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Dispatches pipeline with multiple tests and scan paths in matrix."""
        dispatch_url = f"{API_BASE_URL}projects/12345/trigger/pipeline"
        aioresponses.post(
            dispatch_url,
            status=201,
            payload=create_pipeline_response(pipeline_id=789),
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

        matrix = json.loads(payload["variables"]["MATRIX_TESTS"])
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
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError when dispatch fails."""
        aioresponses.post(
            f"{API_BASE_URL}projects/12345/trigger/pipeline",
            status=400,
            body="Bad Request",
        )

        test_definition = TestDefinitionFactory.build(
            tests=[TestFactory.build(source=TestSourceFactory.build())]
        )

        with pytest.raises(RuntimeError, match="Failed to create pipeline: 400"):
            await provider.dispatch_scanner_tests(
                scanner_id="org/scanner",
                test_definition=test_definition,
                registry_ref="abc123",
                registry_repo="org/registry",
            )

    async def test_raises_on_missing_pipeline_id(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError when pipeline ID is missing from response."""
        aioresponses.post(
            f"{API_BASE_URL}projects/12345/trigger/pipeline",
            status=201,
            payload={"web_url": "https://gitlab.com/project/pipelines/789"},
        )

        test_definition = TestDefinitionFactory.build(
            tests=[TestFactory.build(source=TestSourceFactory.build())]
        )

        with pytest.raises(RuntimeError, match="Pipeline ID not found"):
            await provider.dispatch_scanner_tests(
                scanner_id="org/scanner",
                test_definition=test_definition,
                registry_ref="abc123",
                registry_repo="org/registry",
            )


class TestPollStatus:
    """Tests for poll_status."""

    async def test_returns_none_when_pipeline_running(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns None when pipeline is still running."""
        aioresponses.get(
            f"{API_BASE_URL}projects/12345/pipelines/789",
            payload=pipeline(status="running"),
        )

        result = await provider.poll_status("789")

        assert result is None

    async def test_returns_none_when_pipeline_pending(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns None when pipeline is pending."""
        aioresponses.get(
            f"{API_BASE_URL}projects/12345/pipelines/789",
            payload=pipeline(status="pending"),
        )

        result = await provider.poll_status("789")

        assert result is None

    async def test_returns_results_on_success(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns results when pipeline completes successfully."""
        aioresponses.get(
            f"{API_BASE_URL}projects/12345/pipelines/789",
            payload=pipeline(
                pipeline_id=789,
                status="success",
                web_url="https://gitlab.com/test/project/-/pipelines/789",
                created_at="2099-01-01T12:00:00Z",
                updated_at="2099-01-01T12:01:30Z",
            ),
        )

        results = await provider.poll_status("789")

        assert results is not None
        assert len(results) == 1
        assert results[0].status == "success"
        assert results[0].duration == 90.0
        assert results[0].run_url == "https://gitlab.com/test/project/-/pipelines/789"

    @pytest.mark.parametrize(
        ("gitlab_status", "expected_status"),
        [
            ("success", "success"),
            ("failed", "failure"),
            ("canceled", "error"),
            ("skipped", "error"),
            ("manual", "error"),
        ],
    )
    async def test_maps_status_correctly(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
        gitlab_status: str,
        expected_status: str,
    ) -> None:
        """Maps GitLab pipeline status to test result status."""
        aioresponses.get(
            f"{API_BASE_URL}projects/12345/pipelines/789",
            payload=pipeline(status=gitlab_status),
        )

        results = await provider.poll_status("789")

        assert results is not None
        assert results[0].status == expected_status

    async def test_raises_on_api_error(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Raises RuntimeError on API failure."""
        aioresponses.get(
            f"{API_BASE_URL}projects/12345/pipelines/789",
            status=404,
            body="Not Found",
        )

        with pytest.raises(RuntimeError, match="Failed to get pipeline: 404"):
            await provider.poll_status("789")


class TestGetPipeline:
    """Tests for get_pipeline."""

    async def test_returns_pipeline(
        self,
        provider: GitLabCIProvider,
        aioresponses: aioresponses_cls,
    ) -> None:
        """Returns pipeline model from API response with Bearer token auth."""
        get_url = f"{API_BASE_URL}projects/12345/pipelines/789"
        aioresponses.get(
            get_url,
            payload=pipeline(pipeline_id=789, ref="feature-branch"),
        )

        result = await provider.get_pipeline("789")

        assert result.id == 789
        assert result.ref == "feature-branch"
        assert result.status == "success"

        call = aioresponses.requests[("GET", URL(get_url))][0]
        assert call.kwargs["headers"]["Authorization"] == "Bearer glpat-api-token-456"


class TestProjectIdEncoding:
    """Tests for project ID URL encoding."""

    async def test_encodes_project_path_in_url(
        self,
        aioresponses: aioresponses_cls,
    ) -> None:
        """URL-encodes project path for API calls."""
        config = GitLabCIConfig(
            trigger_token=SecretStr("glptt-trigger-token-123"),
            api_token=SecretStr("glpat-api-token-456"),
            project_id="boostsecurityio/martin/test-runner",
            api_base_url=API_BASE_URL,
        )

        async with GitLabCIProvider.from_config(config) as provider:
            encoded_url = (
                f"{API_BASE_URL}projects/"
                "boostsecurityio%2Fmartin%2Ftest-runner/trigger/pipeline"
            )
            aioresponses.post(
                encoded_url,
                status=201,
                payload=create_pipeline_response(pipeline_id=789),
            )

            test_definition = TestDefinitionFactory.build(
                tests=[TestFactory.build(source=TestSourceFactory.build())]
            )

            pipeline_id = await provider.dispatch_scanner_tests(
                scanner_id="org/scanner",
                test_definition=test_definition,
                registry_ref="abc123",
                registry_repo="org/registry",
            )

            assert pipeline_id == "789"

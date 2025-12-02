"""Tests for test orchestrator."""

from unittest.mock import Mock

import pytest

from scan_test_action.models.result import TestResult
from scan_test_action.orchestrator import TestOrchestrator
from scan_test_action.providers.base import PipelineProvider
from scan_test_action.testing.github.factories import TestDefinitionFactory


@pytest.fixture
def provider_mock() -> Mock:
    """Create mock provider."""
    return Mock(spec=PipelineProvider)


@pytest.fixture
def orchestrator(provider_mock: Mock) -> TestOrchestrator[str]:
    """Create orchestrator with mock provider."""
    return TestOrchestrator(provider=provider_mock)


async def test_returns_empty_when_no_test_definitions(
    orchestrator: TestOrchestrator[str],
    provider_mock: Mock,
) -> None:
    """Returns empty list when no test definitions provided."""
    results = await orchestrator.run_tests(
        test_definitions={},
        registry_repo="org/registry",
        registry_ref="abc123",
    )

    assert results == []
    provider_mock.dispatch_scanner_tests.assert_not_called()


async def test_runs_single_scanner_test(
    orchestrator: TestOrchestrator[str],
    provider_mock: Mock,
) -> None:
    """Runs test for a single scanner and returns results."""
    test_def = TestDefinitionFactory.build()

    provider_mock.dispatch_scanner_tests.return_value = "run-123"
    provider_mock.wait_for_completion.return_value = [
        TestResult(status="success", duration=10.5, run_url="https://example.com")
    ]

    results = await orchestrator.run_tests(
        test_definitions={"org/scanner": test_def},
        registry_repo="org/registry",
        registry_ref="abc123",
    )

    assert len(results) == 1
    assert results[0].scanner_id == "org/scanner"
    assert len(results[0].results) == 1
    assert results[0].results[0].status == "success"

    provider_mock.dispatch_scanner_tests.assert_called_once_with(
        "org/scanner", test_def, "abc123", "org/registry"
    )
    provider_mock.wait_for_completion.assert_called_once_with("run-123")


async def test_runs_multiple_scanners_in_parallel(
    orchestrator: TestOrchestrator[str],
    provider_mock: Mock,
) -> None:
    """Runs tests for multiple scanners in parallel."""
    test_def1 = TestDefinitionFactory.build()
    test_def2 = TestDefinitionFactory.build()

    provider_mock.dispatch_scanner_tests.side_effect = ["run-1", "run-2"]
    provider_mock.wait_for_completion.side_effect = [
        [TestResult(status="success", duration=10.0)],
        [TestResult(status="failure", duration=15.0)],
    ]

    results = await orchestrator.run_tests(
        test_definitions={"scanner1": test_def1, "scanner2": test_def2},
        registry_repo="org/registry",
        registry_ref="abc123",
    )

    assert len(results) == 2
    assert provider_mock.dispatch_scanner_tests.call_count == 2
    assert provider_mock.wait_for_completion.call_count == 2


async def test_handles_exception_during_wait(
    orchestrator: TestOrchestrator[str],
    provider_mock: Mock,
) -> None:
    """Handles exceptions during wait_for_completion and returns error results."""
    test_def = TestDefinitionFactory.build()

    provider_mock.dispatch_scanner_tests.return_value = "run-123"
    provider_mock.wait_for_completion.side_effect = RuntimeError("API Error")

    results = await orchestrator.run_tests(
        test_definitions={"org/scanner": test_def},
        registry_repo="org/registry",
        registry_ref="abc123",
    )

    assert len(results) == 1
    assert results[0].scanner_id == "unknown"
    assert results[0].results[0].status == "error"
    assert results[0].results[0].message == "API Error"


async def test_handles_exception_during_dispatch(
    orchestrator: TestOrchestrator[str],
    provider_mock: Mock,
) -> None:
    """Handles exceptions during dispatch and returns error results."""
    test_def = TestDefinitionFactory.build()

    provider_mock.dispatch_scanner_tests.side_effect = RuntimeError("Dispatch failed")

    results = await orchestrator.run_tests(
        test_definitions={"org/scanner": test_def},
        registry_repo="org/registry",
        registry_ref="abc123",
    )

    assert len(results) == 1
    assert results[0].scanner_id == "unknown"
    assert results[0].results[0].status == "error"
    assert results[0].results[0].message == "Dispatch failed"


async def test_continues_on_partial_failure(
    orchestrator: TestOrchestrator[str],
    provider_mock: Mock,
) -> None:
    """Continues processing when one scanner fails."""
    test_def1 = TestDefinitionFactory.build()
    test_def2 = TestDefinitionFactory.build()

    provider_mock.dispatch_scanner_tests.side_effect = ["run-1", "run-2"]
    provider_mock.wait_for_completion.side_effect = [
        [TestResult(status="success", duration=10.0)],
        RuntimeError("Scanner 2 failed"),
    ]

    results = await orchestrator.run_tests(
        test_definitions={"scanner1": test_def1, "scanner2": test_def2},
        registry_repo="org/registry",
        registry_ref="abc123",
    )

    assert len(results) == 2
    statuses = {r.results[0].status for r in results}
    assert statuses == {"success", "error"}

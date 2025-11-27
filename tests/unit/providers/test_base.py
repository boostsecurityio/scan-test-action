"""Tests for PipelineProvider base class."""

from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

from scan_test_action.models.definition import TestDefinition
from scan_test_action.models.result import TestResult
from scan_test_action.providers.base import PipelineProvider
from scan_test_action.testing.factories import TestResultFactory


@dataclass(frozen=True, kw_only=True)
class MockProvider(PipelineProvider[str]):
    """Test provider that returns configurable poll responses."""

    poll_responses: Sequence[Sequence[TestResult] | None] = field(default_factory=list)
    _poll_count: list[int] = field(default_factory=lambda: [0])

    async def dispatch_scanner_tests(
        self,
        scanner_id: str,
        test_definition: TestDefinition,
        registry_ref: str,
        registry_repo: str,
    ) -> str:  # pragma: no cover
        """Return a mock run ID."""
        return "mock-run-123"

    async def poll_status(
        self,
        dispatch_state: str,
    ) -> Sequence[TestResult] | None:
        """Return next response from poll_responses, then keep returning None."""
        idx = self._poll_count[0]
        self._poll_count[0] += 1
        if idx < len(self.poll_responses):
            return self.poll_responses[idx]
        return None  # Never complete if responses exhausted


class TestWaitForCompletion:
    """Tests for wait_for_completion method."""

    async def test_returns_immediately_when_complete(self) -> None:
        """Returns results immediately when first poll shows complete."""
        expected = [TestResultFactory.build()]
        provider = MockProvider(poll_responses=[expected])

        results = await provider.wait_for_completion("run-123", poll_interval=0.01)

        assert results == expected

    async def test_polls_until_complete(self) -> None:
        """Keeps polling until results returned."""
        expected = [TestResultFactory.build()]
        provider = MockProvider(poll_responses=[None, None, expected])

        results = await provider.wait_for_completion("run-123", poll_interval=0.01)

        assert results == expected
        assert provider._poll_count[0] == 3

    async def test_raises_timeout_error(self) -> None:
        """Raises TimeoutError when timeout exceeded."""
        provider = MockProvider(poll_responses=[None, None, None])

        with pytest.raises(TimeoutError, match="did not complete within"):
            await provider.wait_for_completion(
                "run-123", timeout=0.05, poll_interval=0.02
            )

    async def test_uses_dispatch_state(self) -> None:
        """Passes dispatch_state to poll_status."""
        calls: list[str] = []

        @dataclass(frozen=True, kw_only=True)
        class StateTrackingProvider(PipelineProvider[str]):
            async def dispatch_scanner_tests(
                self,
                scanner_id: str,
                test_definition: TestDefinition,
                registry_ref: str,
                registry_repo: str,
            ) -> str:  # pragma: no cover
                return "tracked-state"

            async def poll_status(
                self,
                dispatch_state: str,
            ) -> Sequence[TestResult] | None:
                calls.append(dispatch_state)
                return []

        provider = StateTrackingProvider()
        await provider.wait_for_completion("my-state", poll_interval=0.01)

        assert calls == ["my-state"]

    async def test_works_with_complex_state(self) -> None:
        """Works with providers that use complex dispatch state."""

        @dataclass(frozen=True)
        class ComplexState:
            run_id: str
            workflow_id: str
            extra_data: dict[str, str]

        @dataclass(frozen=True, kw_only=True)
        class ComplexProvider(PipelineProvider[ComplexState]):
            async def dispatch_scanner_tests(
                self,
                scanner_id: str,
                test_definition: TestDefinition,
                registry_ref: str,
                registry_repo: str,
            ) -> ComplexState:
                return ComplexState(
                    run_id="123",
                    workflow_id="456",
                    extra_data={"scanner": scanner_id},
                )

            async def poll_status(
                self,
                dispatch_state: ComplexState,
            ) -> Sequence[TestResult] | None:
                assert dispatch_state.run_id == "123"
                assert dispatch_state.extra_data["scanner"] == "org/scanner"
                return [TestResultFactory.build()]

        provider = ComplexProvider()
        state = await provider.dispatch_scanner_tests(
            "org/scanner",
            TestDefinition(version="1.0"),
            "abc123",
            "org/registry",
        )
        results = await provider.wait_for_completion(state, poll_interval=0.01)

        assert len(results) == 1

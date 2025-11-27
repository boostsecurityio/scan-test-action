"""Abstract base class for CI/CD pipeline providers."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from scan_test_action.models.definition import TestDefinition
from scan_test_action.models.result import TestResult


@dataclass(frozen=True, kw_only=True)
class PipelineProvider[T](ABC):
    """Abstract base for CI/CD pipeline providers.

    Generic type T represents the dispatch state - whatever data the provider
    needs to pass from dispatch to poll. This could be a simple run ID string,
    or a more complex state object containing multiple identifiers.
    """

    @abstractmethod
    async def dispatch_scanner_tests(
        self,
        scanner_id: str,
        test_definition: TestDefinition,
        registry_ref: str,
        registry_repo: str,
    ) -> T:
        """Dispatch all tests for a scanner and return dispatch state.

        Args:
            scanner_id: Scanner identifier (e.g., "boostsecurityio/trivy-fs")
            test_definition: Complete test definition with all tests
            registry_ref: Git ref of the registry (commit SHA)
            registry_repo: Registry repository in org/repo format

        Returns:
            Dispatch state to pass to poll_status

        """

    @abstractmethod
    async def poll_status(
        self,
        dispatch_state: T,
    ) -> Sequence[TestResult] | None:
        """Check if all tests are complete and get results.

        Args:
            dispatch_state: State returned from dispatch_scanner_tests

        Returns:
            List of results if complete, None if still running

        """

    async def wait_for_completion(
        self,
        dispatch_state: T,
        timeout: float = 1800,
        poll_interval: float = 30,
    ) -> Sequence[TestResult]:
        """Wait for all tests to complete.

        Args:
            dispatch_state: State returned from dispatch_scanner_tests
            timeout: Maximum wait time in seconds (default: 30 minutes)
            poll_interval: Seconds between polls (default: 30)

        Returns:
            List of test results (one per matrix entry)

        Raises:
            TimeoutError: If tests don't complete within timeout

        """
        deadline = asyncio.get_event_loop().time() + timeout

        while True:
            if (results := await self.poll_status(dispatch_state)) is not None:
                return results

            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(f"Tests did not complete within {timeout} seconds")

            await asyncio.sleep(poll_interval)

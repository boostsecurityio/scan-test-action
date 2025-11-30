"""Test orchestrator for coordinating test execution on a single provider."""

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from scan_test_action.models.definition import TestDefinition
from scan_test_action.models.result import TestResult
from scan_test_action.providers.base import PipelineProvider

log = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ScannerResult:
    """Result container for a scanner's test execution."""

    scanner_id: str
    results: Sequence[TestResult]


@dataclass(frozen=True, kw_only=True)
class TestOrchestrator[T]:
    """Orchestrates test execution on a single provider."""

    __test__ = False

    provider: PipelineProvider[T]

    async def run_tests(
        self,
        test_definitions: Mapping[str, TestDefinition],
        registry_repo: str,
        registry_ref: str,
    ) -> Sequence[ScannerResult]:
        """Run all tests for the given scanners on the configured provider.

        Args:
            test_definitions: Test definitions mapped by scanner ID
            registry_repo: Registry repository identifier (org/repo format)
            registry_ref: Git ref of the registry (commit SHA)

        Returns:
            List of scanner results, one per scanner tested

        """
        if not test_definitions:
            log.info("No test definitions provided")
            return []

        log.info("Dispatching tests for %d scanner(s)...", len(test_definitions))
        tasks = [
            self._run_scanner_tests(scanner_id, test_def, registry_ref, registry_repo)
            for scanner_id, test_def in test_definitions.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        log.info("Test execution completed")

        return self._process_results(results)

    def _process_results(
        self,
        results: Sequence[ScannerResult | BaseException],
    ) -> Sequence[ScannerResult]:
        """Process results from test execution, handling exceptions."""
        final_results: list[ScannerResult] = []

        for result in results:
            if isinstance(result, ScannerResult):
                for test_result in result.results:
                    log.info(
                        "Test completed: scanner=%s status=%s duration=%.1fs",
                        result.scanner_id,
                        test_result.status,
                        test_result.duration,
                    )
                final_results.append(result)
            elif isinstance(result, Exception):
                log.error("Scanner test execution failed: %s", result, exc_info=result)
                error_result = ScannerResult(
                    scanner_id="unknown",
                    results=[
                        TestResult(
                            status="error",
                            duration=0.0,
                            message=str(result),
                        )
                    ],
                )
                final_results.append(error_result)

        return final_results

    async def _run_scanner_tests(
        self,
        scanner_id: str,
        test_definition: TestDefinition,
        registry_ref: str,
        registry_repo: str,
    ) -> ScannerResult:
        """Run all tests for a scanner and wait for completion."""
        log.info(
            "Dispatching tests for scanner %s (%d test(s))",
            scanner_id,
            len(test_definition.tests),
        )

        dispatch_state = await self.provider.dispatch_scanner_tests(
            scanner_id, test_definition, registry_ref, registry_repo
        )
        log.info("Tests dispatched for %s, waiting for completion...", scanner_id)

        results = await self.provider.wait_for_completion(dispatch_state)

        return ScannerResult(scanner_id=scanner_id, results=results)

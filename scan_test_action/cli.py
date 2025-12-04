"""CLI entry point for scanner registry test action."""

import argparse
import asyncio
import json
import logging
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scan_test_action.definition_loader import load_test_definition
from scan_test_action.models.definition import TestDefinition
from scan_test_action.orchestrator import ScannerResult, TestOrchestrator
from scan_test_action.providers.loading import load_provider_manifest
from scan_test_action.scanner_detector import get_scanners_to_test

STATUS_SYMBOLS = {
    "success": "✅",
    "failure": "❌",
    "error": "❗",
    "timeout": "⏱️",
}


def log_results_summary(
    log: logging.Logger, scanner_results: Sequence[ScannerResult]
) -> None:
    """Log a formatted summary of test results with pipeline URLs."""
    log.info("=" * 80)
    log.info("Test Results Summary:")
    log.info("=" * 80)

    for scanner_result in scanner_results:
        for test_result in scanner_result.results:
            symbol = STATUS_SYMBOLS.get(test_result.status, "?")
            log.info(
                "%s %s: %s (%.2fs)",
                symbol,
                scanner_result.scanner_id,
                test_result.status,
                test_result.duration,
            )
            if test_result.run_url:
                log.info("  Run URL: %s", test_result.run_url)
            if test_result.message:
                log.info("  Message: %s", test_result.message)


def parse_fallback_scanners(fallback_scanners: str) -> Sequence[str]:
    """Parse comma-separated fallback scanner IDs."""
    if not fallback_scanners.strip():
        return ()
    return tuple(s.strip() for s in fallback_scanners.split(",") if s.strip())


async def run(
    provider_key: str,
    provider_config_json: str,
    registry_path: Path,
    registry_repo: str,
    registry_ref: str,
    base_ref: str,
    fallback_scanners: Sequence[str] = (),
) -> int:
    """Run scanner tests and return exit code."""
    log = logging.getLogger("scan_test_action")

    log.info("Loading provider: %s", provider_key)
    manifest = load_provider_manifest(provider_key)

    config_dict = json.loads(provider_config_json)
    config = manifest.config_cls(**config_dict)

    log.info("Detecting changed scanners (base_ref=%s)", base_ref)
    changed_scanners = await get_scanners_to_test(
        registry_path, base_ref, "HEAD", fallback_scanners
    )

    if not changed_scanners:
        log.info("No changed scanners detected")
        print(json.dumps({"total": 0, "results": []}))
        return 0

    log.info("Changed scanners: %s", ", ".join(changed_scanners))

    log.info("Loading test definitions...")
    test_definitions = await load_test_definitions(registry_path, changed_scanners)

    if not test_definitions:
        log.info("No test definitions found for changed scanners")
        print(json.dumps({"total": 0, "results": []}))
        return 0

    log.info("Running tests for %d scanner(s)...", len(test_definitions))

    async with manifest.provider_factory(config) as provider:
        orchestrator = TestOrchestrator(provider=provider)
        scanner_results = await orchestrator.run_tests(
            test_definitions, registry_repo, registry_ref
        )

    log_results_summary(log, scanner_results)

    output = format_output(scanner_results)
    print(json.dumps(output, indent=2))

    has_failures = any(
        result.status in {"failure", "error", "timeout"}
        for scanner_result in scanner_results
        for result in scanner_result.results
    )

    return 1 if has_failures else 0


async def load_test_definitions(
    registry_path: Path, scanner_ids: Sequence[str]
) -> Mapping[str, TestDefinition]:
    """Load test definitions for the given scanners."""
    definitions: dict[str, TestDefinition] = {}
    for scanner_id in scanner_ids:
        try:
            definitions[scanner_id] = await load_test_definition(
                registry_path, scanner_id
            )
        except FileNotFoundError:
            pass
    return definitions


def format_output(scanner_results: Sequence[ScannerResult]) -> dict[str, Any]:
    """Format scanner results for JSON output."""
    all_results: list[dict[str, Any]] = []
    for scanner_result in scanner_results:
        for test_result in scanner_result.results:
            all_results.append(
                {
                    "scanner": scanner_result.scanner_id,
                    "status": test_result.status,
                    "duration": test_result.duration,
                    "message": test_result.message,
                    "run_url": test_result.run_url,
                }
            )

    return {
        "total": len(all_results),
        "passed": sum(1 for r in all_results if r["status"] == "success"),
        "failed": sum(1 for r in all_results if r["status"] == "failure"),
        "errors": sum(1 for r in all_results if r["status"] == "error"),
        "timeouts": sum(1 for r in all_results if r["status"] == "timeout"),
        "results": all_results,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run scanner tests on CI/CD providers")
    parser.add_argument(
        "--provider",
        required=True,
        help="Provider key (github-actions, gitlab-ci, azure-devops, bitbucket)",
    )
    parser.add_argument(
        "--provider-config",
        required=True,
        help="JSON configuration for the provider",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        required=True,
        help="Path to scanner registry repository",
    )
    parser.add_argument(
        "--registry-repo",
        required=True,
        help="Registry repository identifier (org/repo format)",
    )
    parser.add_argument(
        "--registry-ref",
        required=True,
        help="Git ref of the registry (commit SHA)",
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Base git reference to compare against",
    )
    parser.add_argument(
        "--fallback-scanners",
        default="",
        help="Comma-separated scanner IDs to test when workflow files change",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    exit_code = asyncio.run(
        run(
            provider_key=args.provider,
            provider_config_json=args.provider_config,
            registry_path=args.registry_path,
            registry_repo=args.registry_repo,
            registry_ref=args.registry_ref,
            base_ref=args.base_ref,
            fallback_scanners=parse_fallback_scanners(args.fallback_scanners),
        )
    )
    sys.exit(exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()

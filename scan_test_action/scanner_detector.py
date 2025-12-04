"""Detect modified scanners in a git repository."""

import asyncio
import logging
from collections.abc import Sequence
from pathlib import Path

logger = logging.getLogger(__name__)


async def get_scanners_to_test(
    registry_path: Path,
    base_ref: str,
    head_ref: str,
    fallback_scanners: Sequence[str] = (),
) -> Sequence[str]:
    """Determine which scanners need testing based on changed files.

    Args:
        registry_path: Path to the scanner registry repository
        base_ref: Base git reference (e.g., "origin/main")
        head_ref: Head git reference (e.g., "HEAD")
        fallback_scanners: Scanner IDs to test when workflow files change
            but no scanner files changed

    Returns:
        Scanner identifiers that need testing.

    """
    changed_files = await get_changed_files(registry_path, base_ref, head_ref)
    scanner_ids = extract_scanner_ids(changed_files)

    scanners_with_tests = [
        scanner_id
        for scanner_id in scanner_ids
        if has_test_definition(registry_path, scanner_id)
    ]

    if scanners_with_tests:
        return scanners_with_tests

    if has_workflow_changes(changed_files) and fallback_scanners:
        return sorted(
            scanner_id
            for scanner_id in fallback_scanners
            if has_test_definition(registry_path, scanner_id)
        )

    return []


def has_test_definition(registry_path: Path, scanner_id: str) -> bool:
    """Check if scanner has a tests.yaml file."""
    test_file = registry_path / "scanners" / scanner_id / "tests.yaml"
    return test_file.exists()


async def get_changed_files(
    registry_path: Path,
    base_ref: str,
    head_ref: str,
) -> Sequence[str]:
    """Get list of changed files between two git refs."""
    resolved_base = await resolve_ref(registry_path, base_ref)
    resolved_head = await resolve_ref(registry_path, head_ref)

    process = await asyncio.create_subprocess_exec(
        "git",
        "diff",
        "--name-only",
        resolved_base,
        resolved_head,
        cwd=registry_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"Git diff failed: {stderr.decode().strip()}")

    output = stdout.decode().strip()
    return output.split("\n") if output else []


async def resolve_ref(registry_path: Path, ref: str) -> str:
    """Resolve a git reference, trying origin/ prefix if needed.

    In CI environments like GitHub Actions, refs often exist as origin/main
    instead of main. This function tries both.
    """
    if await ref_exists(registry_path, ref):
        return ref

    if not ref.startswith(("origin/", "refs/")):
        origin_ref = f"origin/{ref}"
        if await ref_exists(registry_path, origin_ref):
            return origin_ref

    raise RuntimeError(f"Cannot resolve git ref '{ref}'")


async def ref_exists(registry_path: Path, ref: str) -> bool:
    """Check if a git reference exists."""
    process = await asyncio.create_subprocess_exec(
        "git",
        "rev-parse",
        "--verify",
        "--quiet",
        ref,
        cwd=registry_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await process.communicate()
    return process.returncode == 0


def extract_scanner_ids(changed_files: Sequence[str]) -> Sequence[str]:
    """Extract unique scanner identifiers from changed file paths.

    Args:
        changed_files: File paths (e.g., ["scanners/org/scanner/module.yaml"])

    Returns:
        Unique scanner identifiers sorted alphabetically (e.g., ["org/scanner"])

    """
    scanner_ids: set[str] = set()

    for file_path in changed_files:
        if not file_path.startswith("scanners/"):
            continue

        parts = Path(file_path).parts
        if len(parts) >= 4:  # scanners / org / scanner / file
            scanner_ids.add(f"{parts[1]}/{parts[2]}")

    return sorted(scanner_ids)


def has_workflow_changes(changed_files: Sequence[str]) -> bool:
    """Check if any workflow files have changed."""
    return any(
        file_path.startswith(".github/workflows/") for file_path in changed_files
    )

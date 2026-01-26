"""Load and parse test definitions from YAML files."""

from collections.abc import Sequence
from pathlib import Path

import yaml

from scan_test_action.models.definition import TestDefinition


async def load_test_definition(
    registry_path: Path,
    scanner_id: str,
    allowed_env_prefixes: Sequence[str] = (),
) -> TestDefinition:
    """Load test definition for a scanner.

    Args:
        registry_path: Path to the scanner registry repository
        scanner_id: Scanner identifier (e.g., "boostsecurityio/trivy-fs")
        allowed_env_prefixes: CLI-provided allowed env prefixes (overrides YAML)

    Returns:
        Parsed test definition

    Raises:
        FileNotFoundError: If tests.yaml doesn't exist
        ValueError: If YAML is invalid or doesn't match schema

    """
    test_file = registry_path / "scanners" / scanner_id / "tests.yaml"

    if not test_file.exists():
        raise FileNotFoundError(f"Test file not found: {test_file}")

    try:
        with test_file.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {test_file}: {e}") from e

    if data is None:
        raise ValueError(f"Empty test file: {test_file}")

    try:
        definition = TestDefinition.model_validate(data)
    except Exception as e:
        raise ValueError(f"Invalid test definition schema in {test_file}: {e}") from e

    # Validate env vars against CLI-provided prefixes
    validate_env_prefixes(definition, allowed_env_prefixes, test_file)

    return definition


def validate_env_prefixes(
    definition: TestDefinition,
    allowed_env_prefixes: Sequence[str],
    test_file: Path,
) -> None:
    """Validate that all env vars in tests match allowed prefixes.

    Args:
        definition: The parsed test definition
        allowed_env_prefixes: CLI-provided allowed env prefixes
        test_file: Path to the test file (for error messages)

    Raises:
        ValueError: If env vars don't match allowed prefixes

    """
    for test in definition.tests:
        if not test.env:
            continue

        if not allowed_env_prefixes:
            raise ValueError(
                f"{test_file}: env vars specified but no allowed_env_prefixes defined"
            )

        for key in test.env.keys():
            if not any(key.startswith(prefix) for prefix in allowed_env_prefixes):
                raise ValueError(
                    f"{test_file}: Environment variable '{key}' does not match any "
                    f"allowed prefix: {list(allowed_env_prefixes)}"
                )

"""Models for test definitions loaded from tests.yaml files."""

from collections.abc import Mapping, Sequence
from typing import Literal, Self

from pydantic import Field, model_validator

from scan_test_action.models.base import Model


class TestSource(Model):
    """Source repository configuration for a test."""

    __test__ = False

    url: str = Field(..., description="Git repository URL (HTTPS only)")
    ref: str = Field(..., description="Git reference (branch, tag, or commit SHA)")


class Test(Model):
    """Individual test specification."""

    __test__ = False

    name: str = Field(..., description="Human-readable test name")
    type: Literal["source-code", "container-image"] = Field(
        ..., description="Type of test to execute"
    )
    source: TestSource = Field(..., description="Source repository details")
    scan_paths: Sequence[str] = Field(
        default_factory=list,
        description="Paths to scan (empty means scan entire repo)",
    )
    timeout: str = Field(default="5m", description="Test timeout (e.g., '300s', '5m')")
    env: Mapping[str, str] = Field(
        default_factory=dict,
        description="Environment variables to pass to the test runner",
    )


class MatrixEntry(Model):
    """Single matrix entry representing one (test, scan_path) combination."""

    __test__ = False

    test_name: str = Field(..., description="Test name")
    test_type: Literal["source-code", "container-image"] = Field(
        ..., description="Type of test"
    )
    source_url: str = Field(..., description="Git repository URL")
    source_ref: str = Field(..., description="Git reference")
    scan_path: str | None = Field(
        default=None, description="Single scan path (None means scan entire repo)"
    )
    timeout: str = Field(default="5m", description="Test timeout")
    env: Mapping[str, str] = Field(
        default_factory=dict,
        description="Environment variables for this test",
    )


class TestDefinition(Model):
    """Complete test definition loaded from tests.yaml."""

    __test__ = False

    version: str = Field(..., description="Test definition schema version")
    allowed_env_prefixes: Sequence[str] = Field(
        default_factory=list,
        description="List of allowed environment variable name prefixes",
    )
    tests: Sequence[Test] = Field(default_factory=list, description="List of tests")

    @model_validator(mode="after")
    def validate_env_prefixes(self) -> Self:  # noqa: N804
        """Validate that all env vars in tests match allowed prefixes."""
        if not self.allowed_env_prefixes:
            for test in self.tests:
                if test.env:
                    raise ValueError(
                        "env vars specified but no allowed_env_prefixes defined"
                    )
            return self

        for test in self.tests:
            for key in test.env.keys():
                if not any(
                    key.startswith(prefix) for prefix in self.allowed_env_prefixes
                ):
                    raise ValueError(
                        f"Environment variable '{key}' does not match any allowed "
                        f"prefix: {list(self.allowed_env_prefixes)}"
                    )
        return self

    def to_matrix_entries(self) -> Sequence[MatrixEntry]:
        """Convert all tests into matrix entries (one per test/scan_path combo).

        If scan_paths is empty, creates a single entry with scan_path=None,
        indicating the entire repository should be scanned.
        """
        entries: list[MatrixEntry] = []
        for test in self.tests:
            scan_paths: list[str | None] = (
                list(test.scan_paths) if test.scan_paths else [None]
            )
            for scan_path in scan_paths:
                entries.append(
                    MatrixEntry(
                        test_name=test.name,
                        test_type=test.type,
                        source_url=test.source.url,
                        source_ref=test.source.ref,
                        scan_path=scan_path,
                        timeout=test.timeout,
                        env=test.env,
                    )
                )
        return entries

"""Models for test definitions loaded from tests.yaml files."""

from collections.abc import Sequence
from typing import Literal

from pydantic import Field

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
        default_factory=lambda: ["."],
        description="Paths to scan within the repository",
    )
    timeout: str = Field(default="5m", description="Test timeout (e.g., '300s', '5m')")


class MatrixEntry(Model):
    """Single matrix entry representing one (test, scan_path) combination."""

    __test__ = False

    test_name: str = Field(..., description="Test name")
    test_type: Literal["source-code", "container-image"] = Field(
        ..., description="Type of test"
    )
    source_url: str = Field(..., description="Git repository URL")
    source_ref: str = Field(..., description="Git reference")
    scan_path: str = Field(..., description="Single scan path")
    timeout: str = Field(default="5m", description="Test timeout")


class TestDefinition(Model):
    """Complete test definition loaded from tests.yaml."""

    __test__ = False

    version: str = Field(..., description="Test definition schema version")
    tests: Sequence[Test] = Field(default_factory=list, description="List of tests")

    def to_matrix_entries(self) -> Sequence[MatrixEntry]:
        """Convert all tests into matrix entries (one per test/scan_path combo)."""
        entries: list[MatrixEntry] = []
        for test in self.tests:
            for scan_path in test.scan_paths:
                entries.append(
                    MatrixEntry(
                        test_name=test.name,
                        test_type=test.type,
                        source_url=test.source.url,
                        source_ref=test.source.ref,
                        scan_path=scan_path,
                        timeout=test.timeout,
                    )
                )
        return entries

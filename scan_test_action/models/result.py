"""Models for test execution results."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class TestResult:
    """Result of a single test execution."""

    __test__ = False

    scanner_id: str
    test_name: str
    scan_path: str
    status: Literal["success", "failure", "timeout", "error"]
    duration: float
    message: str | None = None
    run_url: str | None = None

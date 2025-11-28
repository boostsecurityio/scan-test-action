"""Models for test execution results."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, kw_only=True)
class TestResult:
    """Result of a single test execution.

    Contains only execution outcome - the caller knows scanner/test/path context.
    """

    __test__ = False

    status: Literal["success", "failure", "timeout", "error"]
    duration: float
    message: str | None = None
    run_url: str | None = None

"""Fixtures for integration tests."""

import subprocess
from pathlib import Path
from typing import Protocol

import pytest


class CommitFn(Protocol):
    """Protocol for git commit function."""

    def __call__(self, message: str) -> str:
        """Create a commit and return its SHA."""


class CreateScannerFn(Protocol):
    """Protocol for scanner creation function."""

    def __call__(self, scanner_id: str, *, with_tests: bool = False) -> Path:
        """Create a scanner directory and return its path."""


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create an initialized git repository."""
    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return tmp_path


@pytest.fixture
def git_commit(git_repo: Path) -> CommitFn:
    """Return a function to create commits in the test repo."""

    def _commit(message: str) -> str:
        subprocess.run(
            ["git", "add", "-A"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", message],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=git_repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    return _commit


@pytest.fixture
def create_scanner(git_repo: Path) -> CreateScannerFn:
    """Return a function to create scanner directories."""

    def _create(scanner_id: str, *, with_tests: bool = False) -> Path:
        scanner_dir = git_repo / "scanners" / scanner_id
        scanner_dir.mkdir(parents=True, exist_ok=True)
        (scanner_dir / "module.yaml").write_text("name: test\n")
        if with_tests:
            (scanner_dir / "tests.yaml").write_text("version: '1.0'\n")
        return scanner_dir

    return _create

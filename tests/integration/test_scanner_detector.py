"""Integration tests for scanner detector using real git repositories."""

import subprocess
from pathlib import Path

import pytest

from scan_test_action.scanner_detector import (
    extract_scanner_ids,
    get_changed_files,
    get_scanners_to_test,
    has_test_definition,
    has_workflow_changes,
    ref_exists,
    resolve_ref,
)

from .conftest import CommitFn, CreateScannerFn


class TestGetScannersToTest:
    """Tests for get_scanners_to_test."""

    async def test_returns_scanners_with_tests(
        self,
        git_repo: Path,
        git_commit: CommitFn,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Returns only changed scanners that have tests.yaml."""
        base = git_commit("initial")

        create_scanner("org/with-tests", with_tests=True)
        create_scanner("org/without-tests", with_tests=False)
        git_commit("add scanners")

        result = await get_scanners_to_test(git_repo, base, "HEAD")

        assert result == ["org/with-tests"]

    async def test_returns_multiple_scanners_sorted(
        self,
        git_repo: Path,
        git_commit: CommitFn,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Returns multiple scanners in alphabetical order."""
        base = git_commit("initial")

        create_scanner("zorg/zebra", with_tests=True)
        create_scanner("aorg/apple", with_tests=True)
        create_scanner("morg/mango", with_tests=True)
        git_commit("add scanners")

        result = await get_scanners_to_test(git_repo, base, "HEAD")

        assert result == ["aorg/apple", "morg/mango", "zorg/zebra"]

    async def test_returns_empty_when_no_changes(
        self,
        git_repo: Path,
        git_commit: CommitFn,
    ) -> None:
        """Returns empty list when no files changed."""
        commit = git_commit("initial")

        result = await get_scanners_to_test(git_repo, commit, "HEAD")

        assert result == []

    async def test_returns_empty_when_no_tests(
        self,
        git_repo: Path,
        git_commit: CommitFn,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Returns empty list when changed scanners have no tests."""
        base = git_commit("initial")

        create_scanner("org/scanner", with_tests=False)
        git_commit("add scanner")

        result = await get_scanners_to_test(git_repo, base, "HEAD")

        assert result == []

    async def test_ignores_non_scanner_changes(
        self,
        git_repo: Path,
        git_commit: CommitFn,
    ) -> None:
        """Returns empty list when only non-scanner files changed."""
        base = git_commit("initial")

        (git_repo / "README.md").write_text("docs")
        git_commit("update readme")

        result = await get_scanners_to_test(git_repo, base, "HEAD")

        assert result == []

    async def test_returns_fallback_scanners_on_workflow_change(
        self,
        git_repo: Path,
        git_commit: CommitFn,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Returns fallback scanners when workflow files change."""
        create_scanner("org/fallback-scanner", with_tests=True)
        base = git_commit("initial with scanner")

        workflows_dir = git_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: test")
        git_commit("add workflow")

        result = await get_scanners_to_test(
            git_repo, base, "HEAD", fallback_scanners=["org/fallback-scanner"]
        )

        assert result == ["org/fallback-scanner"]

    async def test_returns_multiple_fallback_scanners_sorted(
        self,
        git_repo: Path,
        git_commit: CommitFn,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Returns multiple fallback scanners in sorted order."""
        create_scanner("zorg/zebra", with_tests=True)
        create_scanner("aorg/apple", with_tests=True)
        base = git_commit("initial with scanners")

        workflows_dir = git_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: test")
        git_commit("add workflow")

        result = await get_scanners_to_test(
            git_repo, base, "HEAD", fallback_scanners=["zorg/zebra", "aorg/apple"]
        )

        assert result == ["aorg/apple", "zorg/zebra"]

    async def test_ignores_fallback_without_tests(
        self,
        git_repo: Path,
        git_commit: CommitFn,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Ignores fallback scanners that don't have tests.yaml."""
        create_scanner("org/with-tests", with_tests=True)
        create_scanner("org/without-tests", with_tests=False)
        base = git_commit("initial with scanners")

        workflows_dir = git_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: test")
        git_commit("add workflow")

        result = await get_scanners_to_test(
            git_repo,
            base,
            "HEAD",
            fallback_scanners=["org/with-tests", "org/without-tests"],
        )

        assert result == ["org/with-tests"]

    async def test_scanner_changes_take_precedence_over_fallback(
        self,
        git_repo: Path,
        git_commit: CommitFn,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Changed scanners take precedence over fallback scanners."""
        create_scanner("org/fallback", with_tests=True)
        base = git_commit("initial with fallback scanner")

        create_scanner("org/changed", with_tests=True)
        workflows_dir = git_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: test")
        git_commit("add scanner and workflow")

        result = await get_scanners_to_test(
            git_repo, base, "HEAD", fallback_scanners=["org/fallback"]
        )

        assert result == ["org/changed"]

    async def test_no_fallback_without_workflow_change(
        self,
        git_repo: Path,
        git_commit: CommitFn,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Does not return fallback scanners when no workflow files changed."""
        create_scanner("org/fallback", with_tests=True)
        base = git_commit("initial with scanner")

        (git_repo / "README.md").write_text("docs")
        git_commit("update readme")

        result = await get_scanners_to_test(
            git_repo, base, "HEAD", fallback_scanners=["org/fallback"]
        )

        assert result == []

    async def test_empty_fallback_parameter(
        self,
        git_repo: Path,
        git_commit: CommitFn,
    ) -> None:
        """Returns empty list when fallback_scanners is empty."""
        base = git_commit("initial")

        workflows_dir = git_repo / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "test.yml").write_text("name: test")
        git_commit("add workflow")

        result = await get_scanners_to_test(
            git_repo, base, "HEAD", fallback_scanners=[]
        )

        assert result == []


class TestHasTestDefinition:
    """Tests for has_test_definition."""

    def test_returns_true_when_exists(
        self,
        git_repo: Path,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Returns True when tests.yaml exists."""
        create_scanner("org/scanner", with_tests=True)

        assert has_test_definition(git_repo, "org/scanner") is True

    def test_returns_false_when_missing(
        self,
        git_repo: Path,
        create_scanner: CreateScannerFn,
    ) -> None:
        """Returns False when tests.yaml doesn't exist."""
        create_scanner("org/scanner", with_tests=False)

        assert has_test_definition(git_repo, "org/scanner") is False


class TestGetChangedFiles:
    """Tests for get_changed_files."""

    async def test_returns_changed_files(
        self,
        git_repo: Path,
        git_commit: CommitFn,
    ) -> None:
        """Returns list of files changed between commits."""
        base = git_commit("initial")

        (git_repo / "file1.txt").write_text("content")
        (git_repo / "file2.txt").write_text("content")
        git_commit("add files")

        changed = await get_changed_files(git_repo, base, "HEAD")

        assert sorted(changed) == ["file1.txt", "file2.txt"]

    async def test_returns_empty_for_no_changes(
        self,
        git_repo: Path,
        git_commit: CommitFn,
    ) -> None:
        """Returns empty list when no files changed."""
        commit = git_commit("initial")

        changed = await get_changed_files(git_repo, commit, "HEAD")

        assert changed == []

    async def test_raises_for_invalid_ref(
        self,
        git_repo: Path,
        git_commit: CommitFn,
    ) -> None:
        """Raises RuntimeError for invalid git ref."""
        git_commit("initial")

        with pytest.raises(RuntimeError, match="Cannot resolve git ref"):
            await get_changed_files(git_repo, "invalid", "HEAD")

    async def test_raises_when_git_diff_fails(
        self,
        git_repo: Path,
        git_commit: CommitFn,
    ) -> None:
        """Raises RuntimeError when git diff fails with valid-looking refs."""
        git_commit("initial")

        # Create a ref pointing to a blob (not a commit)
        # git rev-parse --verify will accept it, but git diff will fail
        result = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=git_repo,
            input="test content",
            capture_output=True,
            text=True,
            check=True,
        )
        blob_sha = result.stdout.strip()

        subprocess.run(
            ["git", "update-ref", "refs/blob-ref", blob_sha],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        with pytest.raises(RuntimeError, match="Git diff failed"):
            await get_changed_files(git_repo, "HEAD", "refs/blob-ref")


class TestResolveRef:
    """Tests for resolve_ref."""

    async def test_resolves_head(self, git_repo: Path, git_commit: CommitFn) -> None:
        """Resolves HEAD directly."""
        git_commit("initial")

        resolved = await resolve_ref(git_repo, "HEAD")

        assert resolved == "HEAD"

    async def test_resolves_commit_sha(
        self, git_repo: Path, git_commit: CommitFn
    ) -> None:
        """Resolves a commit SHA directly."""
        sha = git_commit("initial")

        resolved = await resolve_ref(git_repo, sha)

        assert resolved == sha

    async def test_raises_for_unknown_ref(
        self, git_repo: Path, git_commit: CommitFn
    ) -> None:
        """Raises RuntimeError for unknown refs."""
        git_commit("initial")

        with pytest.raises(RuntimeError, match="Cannot resolve git ref"):
            await resolve_ref(git_repo, "unknown-branch")

    async def test_tries_origin_prefix(
        self, git_repo: Path, git_commit: CommitFn
    ) -> None:
        """Tries origin/ prefix when ref doesn't exist directly."""
        git_commit("initial")

        # Create a remote ref that only exists with origin/ prefix
        subprocess.run(
            ["git", "update-ref", "refs/remotes/origin/test-branch", "HEAD"],
            cwd=git_repo,
            check=True,
            capture_output=True,
        )

        resolved = await resolve_ref(git_repo, "test-branch")

        assert resolved == "origin/test-branch"


class TestRefExists:
    """Tests for ref_exists."""

    async def test_existing_ref(self, git_repo: Path, git_commit: CommitFn) -> None:
        """Returns True for an existing ref."""
        git_commit("initial")

        assert await ref_exists(git_repo, "HEAD") is True

    async def test_non_existing_ref(self, git_repo: Path, git_commit: CommitFn) -> None:
        """Returns False for a non-existing ref."""
        git_commit("initial")

        assert await ref_exists(git_repo, "non-existent") is False


class TestExtractScannerIds:
    """Tests for extract_scanner_ids."""

    def test_extracts_single_scanner(self) -> None:
        """Extracts scanner id from scanner file path."""
        files = ["scanners/org/scanner/module.yaml"]

        result = extract_scanner_ids(files)

        assert result == ["org/scanner"]

    def test_extracts_multiple_scanners(self) -> None:
        """Extracts multiple unique scanner ids."""
        files = [
            "scanners/org1/scanner1/module.yaml",
            "scanners/org2/scanner2/tests.yaml",
            "scanners/org1/scanner1/rules.yaml",  # duplicate
        ]

        result = extract_scanner_ids(files)

        assert result == ["org1/scanner1", "org2/scanner2"]

    def test_ignores_non_scanner_files(self) -> None:
        """Ignores files outside scanners directory."""
        files = [
            "README.md",
            ".github/workflows/test.yml",
            "scanners/org/scanner/module.yaml",
        ]

        result = extract_scanner_ids(files)

        assert result == ["org/scanner"]

    def test_ignores_shallow_paths(self) -> None:
        """Ignores paths that don't reach scanner level."""
        files = [
            "scanners/README.md",
            "scanners/org/README.md",
        ]

        result = extract_scanner_ids(files)

        assert result == []

    def test_returns_sorted(self) -> None:
        """Returns scanner ids in sorted order."""
        files = [
            "scanners/z-org/scanner/file.yaml",
            "scanners/a-org/scanner/file.yaml",
        ]

        result = extract_scanner_ids(files)

        assert result == ["a-org/scanner", "z-org/scanner"]


class TestHasWorkflowChanges:
    """Tests for has_workflow_changes."""

    def test_returns_true_for_workflow_file(self) -> None:
        """Returns True when workflow files are in changed files."""
        files = [".github/workflows/test.yml"]

        assert has_workflow_changes(files) is True

    def test_returns_true_for_nested_workflow_file(self) -> None:
        """Returns True for files nested under .github/workflows/."""
        files = [".github/workflows/ci/build.yml"]

        assert has_workflow_changes(files) is True

    def test_returns_false_for_non_workflow_files(self) -> None:
        """Returns False when no workflow files changed."""
        files = ["README.md", "scanners/org/scanner/module.yaml"]

        assert has_workflow_changes(files) is False

    def test_returns_false_for_github_non_workflow(self) -> None:
        """Returns False for .github files outside workflows."""
        files = [".github/CODEOWNERS", ".github/dependabot.yml"]

        assert has_workflow_changes(files) is False

    def test_returns_false_for_empty_list(self) -> None:
        """Returns False for empty file list."""
        assert has_workflow_changes([]) is False

"""Tests for definition loader."""

from pathlib import Path

import pytest

from scan_test_action.definition_loader import load_test_definition


class TestLoadTestDefinition:
    """Tests for load_test_definition function."""

    __test__ = True  # Explicitly mark as test class despite "Test" prefix

    async def test_loads_valid_yaml(self, tmp_path: Path) -> None:
        """Loads and parses valid tests.yaml file."""
        scanner_dir = tmp_path / "scanners" / "org" / "scanner"
        scanner_dir.mkdir(parents=True)
        (scanner_dir / "tests.yaml").write_text(
            """
version: "1.0"
tests:
  - name: "smoke test"
    type: "source-code"
    source:
      url: "https://github.com/org/repo.git"
      ref: "main"
    scan_paths:
      - "."
    timeout: "5m"
"""
        )

        definition = await load_test_definition(tmp_path, "org/scanner")

        assert definition.version == "1.0"
        assert len(definition.tests) == 1
        assert definition.tests[0].name == "smoke test"
        assert definition.tests[0].type == "source-code"
        assert definition.tests[0].source.url == "https://github.com/org/repo.git"
        assert definition.tests[0].source.ref == "main"

    async def test_loads_multiple_tests(self, tmp_path: Path) -> None:
        """Handles multiple tests in definition."""
        scanner_dir = tmp_path / "scanners" / "org" / "scanner"
        scanner_dir.mkdir(parents=True)
        (scanner_dir / "tests.yaml").write_text(
            """
version: "1.0"
tests:
  - name: "test1"
    type: "source-code"
    source:
      url: "https://github.com/org/repo1.git"
      ref: "main"
  - name: "test2"
    type: "container-image"
    source:
      url: "https://github.com/org/repo2.git"
      ref: "v1.0"
"""
        )

        definition = await load_test_definition(tmp_path, "org/scanner")

        assert len(definition.tests) == 2
        assert definition.tests[0].name == "test1"
        assert definition.tests[1].name == "test2"

    async def test_raises_for_missing_file(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for missing tests.yaml."""
        with pytest.raises(FileNotFoundError, match="Test file not found"):
            await load_test_definition(tmp_path, "org/nonexistent")

    async def test_raises_for_invalid_yaml(self, tmp_path: Path) -> None:
        """Raises ValueError for malformed YAML."""
        scanner_dir = tmp_path / "scanners" / "org" / "scanner"
        scanner_dir.mkdir(parents=True)
        (scanner_dir / "tests.yaml").write_text("invalid: yaml: content: [")

        with pytest.raises(ValueError, match="Invalid YAML"):
            await load_test_definition(tmp_path, "org/scanner")

    async def test_raises_for_empty_file(self, tmp_path: Path) -> None:
        """Raises ValueError for empty tests.yaml."""
        scanner_dir = tmp_path / "scanners" / "org" / "scanner"
        scanner_dir.mkdir(parents=True)
        (scanner_dir / "tests.yaml").write_text("")

        with pytest.raises(ValueError, match="Empty test file"):
            await load_test_definition(tmp_path, "org/scanner")

    async def test_raises_for_invalid_schema(self, tmp_path: Path) -> None:
        """Raises ValueError for schema validation errors."""
        scanner_dir = tmp_path / "scanners" / "org" / "scanner"
        scanner_dir.mkdir(parents=True)
        (scanner_dir / "tests.yaml").write_text(
            """
version: "1.0"
tests:
  - name: "test"
    type: "invalid-type"
    source:
      url: "https://github.com/org/repo.git"
      ref: "main"
"""
        )

        with pytest.raises(ValueError, match="Invalid test definition schema"):
            await load_test_definition(tmp_path, "org/scanner")

    async def test_raises_for_missing_required_fields(self, tmp_path: Path) -> None:
        """Raises ValueError when required fields are missing."""
        scanner_dir = tmp_path / "scanners" / "org" / "scanner"
        scanner_dir.mkdir(parents=True)
        (scanner_dir / "tests.yaml").write_text(
            """
tests:
  - name: "test"
    type: "source-code"
"""
        )

        with pytest.raises(ValueError, match="Invalid test definition schema"):
            await load_test_definition(tmp_path, "org/scanner")

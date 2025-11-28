"""Tests for TestDefinition.to_matrix_entries method."""

from scan_test_action.models.definition import (
    MatrixEntry,
    Test,
    TestDefinition,
    TestSource,
)


def test_single_test_single_path() -> None:
    """Creates one entry for test with single scan path."""
    definition = TestDefinition(
        version="1.0",
        tests=[
            Test(
                name="smoke test",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
                scan_paths=["."],
            )
        ],
    )

    entries = definition.to_matrix_entries()

    assert entries == [
        MatrixEntry(
            test_name="smoke test",
            test_type="source-code",
            source_url="https://github.com/org/repo.git",
            source_ref="main",
            scan_path=".",
            timeout="5m",
        )
    ]


def test_single_test_multiple_paths() -> None:
    """Creates one entry per scan path for test with multiple paths."""
    definition = TestDefinition(
        version="1.0",
        tests=[
            Test(
                name="multi-path test",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
                scan_paths=["src", "lib", "tests"],
            )
        ],
    )

    entries = definition.to_matrix_entries()

    assert len(entries) == 3
    assert entries[0].scan_path == "src"
    assert entries[1].scan_path == "lib"
    assert entries[2].scan_path == "tests"
    assert all(e.test_name == "multi-path test" for e in entries)


def test_multiple_tests() -> None:
    """Creates entries for all tests in definition."""
    definition = TestDefinition(
        version="1.0",
        tests=[
            Test(
                name="test1",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo1.git", ref="main"),
            ),
            Test(
                name="test2",
                type="container-image",
                source=TestSource(url="https://github.com/org/repo2.git", ref="v1.0"),
            ),
        ],
    )

    entries = definition.to_matrix_entries()

    assert len(entries) == 2
    assert entries[0].test_name == "test1"
    assert entries[0].test_type == "source-code"
    assert entries[1].test_name == "test2"
    assert entries[1].test_type == "container-image"


def test_preserves_timeout() -> None:
    """Preserves custom timeout in matrix entries."""
    definition = TestDefinition(
        version="1.0",
        tests=[
            Test(
                name="slow test",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
                timeout="30m",
            )
        ],
    )

    entries = definition.to_matrix_entries()

    assert entries[0].timeout == "30m"


def test_empty_tests() -> None:
    """Returns empty list for definition with no tests."""
    definition = TestDefinition(version="1.0", tests=[])

    entries = definition.to_matrix_entries()

    assert entries == []


def test_default_scan_paths() -> None:
    """Test without explicit scan_paths defaults to root."""
    definition = TestDefinition(
        version="1.0",
        tests=[
            Test(
                name="default paths test",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
            )
        ],
    )

    entries = definition.to_matrix_entries()

    assert entries[0].scan_path == "."

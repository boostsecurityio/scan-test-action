"""Tests for TestDefinition.to_matrix_entries method."""

import pytest

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
                scan_paths=["src"],
            ),
            Test(
                name="test2",
                type="container-image",
                source=TestSource(url="https://github.com/org/repo2.git", ref="v1.0"),
                scan_paths=["app"],
            ),
        ],
    )

    entries = definition.to_matrix_entries()

    assert len(entries) == 2
    assert entries[0].test_name == "test1"
    assert entries[0].test_type == "source-code"
    assert entries[0].scan_path == "src"
    assert entries[1].test_name == "test2"
    assert entries[1].test_type == "container-image"
    assert entries[1].scan_path == "app"


def test_preserves_timeout() -> None:
    """Preserves custom timeout in matrix entries."""
    definition = TestDefinition(
        version="1.0",
        tests=[
            Test(
                name="slow test",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
                scan_paths=["src"],
                timeout="30m",
            )
        ],
    )

    entries = definition.to_matrix_entries()

    assert entries[0].timeout == "30m"
    assert entries[0].scan_path == "src"


def test_empty_tests() -> None:
    """Returns empty list for definition with no tests."""
    definition = TestDefinition(version="1.0", tests=[])

    entries = definition.to_matrix_entries()

    assert entries == []


def test_default_scan_paths() -> None:
    """Test without explicit scan_paths produces scan_path=None (scan entire repo)."""
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

    assert entries[0].scan_path is None


def test_explicit_empty_scan_paths() -> None:
    """Explicit empty scan_paths produces scan_path=None (scan entire repo)."""
    definition = TestDefinition(
        version="1.0",
        tests=[
            Test(
                name="explicit empty paths",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
                scan_paths=[],
            )
        ],
    )

    entries = definition.to_matrix_entries()

    assert len(entries) == 1
    assert entries[0].scan_path is None


def test_scan_path_none_serializes_to_null() -> None:
    """scan_path=None serializes to null in JSON for pipeline consumption."""
    entry = MatrixEntry(
        test_name="test",
        test_type="source-code",
        source_url="https://github.com/org/repo.git",
        source_ref="main",
        scan_path=None,
        timeout="5m",
    )

    data = entry.model_dump(mode="json")

    assert data["scan_path"] is None


def test_env_propagated_to_matrix_entries() -> None:
    """Env vars are correctly propagated from Test to MatrixEntry."""
    definition = TestDefinition(
        version="1.0",
        allowed_env_prefixes=["CODEQL_"],
        tests=[
            Test(
                name="codeql test",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
                env={"CODEQL_LANGUAGE": "javascript"},
            )
        ],
    )

    entries = definition.to_matrix_entries()

    assert entries[0].env == {"CODEQL_LANGUAGE": "javascript"}


def test_env_validation_passes_with_matching_prefix() -> None:
    """Validation passes when env vars match allowed prefixes."""
    definition = TestDefinition(
        version="1.0",
        allowed_env_prefixes=["CODEQL_", "SCANNER_"],
        tests=[
            Test(
                name="test",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
                env={"CODEQL_LANGUAGE": "python", "SCANNER_DEBUG": "true"},
            )
        ],
    )

    assert definition.tests[0].env == {
        "CODEQL_LANGUAGE": "python",
        "SCANNER_DEBUG": "true",
    }


def test_env_validation_fails_with_non_matching_prefix() -> None:
    """Validation fails when env vars don't match any allowed prefix."""
    with pytest.raises(ValueError, match=r"INVALID_VAR.*does not match any allowed"):
        TestDefinition(
            version="1.0",
            allowed_env_prefixes=["CODEQL_"],
            tests=[
                Test(
                    name="test",
                    type="source-code",
                    source=TestSource(
                        url="https://github.com/org/repo.git", ref="main"
                    ),
                    env={"INVALID_VAR": "value"},
                )
            ],
        )


def test_env_validation_fails_when_no_allowed_prefixes_defined() -> None:
    """Validation fails when env vars used but no allowed_env_prefixes defined."""
    with pytest.raises(ValueError, match="no allowed_env_prefixes defined"):
        TestDefinition(
            version="1.0",
            tests=[
                Test(
                    name="test",
                    type="source-code",
                    source=TestSource(
                        url="https://github.com/org/repo.git", ref="main"
                    ),
                    env={"SOME_VAR": "value"},
                )
            ],
        )


def test_env_defaults_to_empty_dict() -> None:
    """Test without explicit env produces empty dict."""
    definition = TestDefinition(
        version="1.0",
        tests=[
            Test(
                name="test",
                type="source-code",
                source=TestSource(url="https://github.com/org/repo.git", ref="main"),
            )
        ],
    )

    entries = definition.to_matrix_entries()

    assert entries[0].env == {}


def test_env_serialization_to_json() -> None:
    """Env serializes correctly to JSON for pipeline consumption."""
    entry = MatrixEntry(
        test_name="test",
        test_type="source-code",
        source_url="https://github.com/org/repo.git",
        source_ref="main",
        env={"CODEQL_LANGUAGE": "javascript", "CODEQL_DEBUG": "true"},
    )

    data = entry.model_dump(mode="json")

    assert data["env"] == {"CODEQL_LANGUAGE": "javascript", "CODEQL_DEBUG": "true"}


def test_multiple_tests_with_different_envs() -> None:
    """Multiple tests can have different env vars, validated against same prefixes."""
    definition = TestDefinition(
        version="1.0",
        allowed_env_prefixes=["CODEQL_"],
        tests=[
            Test(
                name="js-test",
                type="source-code",
                source=TestSource(url="https://github.com/org/js-repo.git", ref="main"),
                env={"CODEQL_LANGUAGE": "javascript"},
            ),
            Test(
                name="py-test",
                type="source-code",
                source=TestSource(url="https://github.com/org/py-repo.git", ref="main"),
                env={"CODEQL_LANGUAGE": "python"},
            ),
        ],
    )

    entries = definition.to_matrix_entries()

    assert entries[0].env == {"CODEQL_LANGUAGE": "javascript"}
    assert entries[1].env == {"CODEQL_LANGUAGE": "python"}

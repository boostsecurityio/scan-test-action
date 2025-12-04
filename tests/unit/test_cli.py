"""Tests for CLI module."""

import logging
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from scan_test_action.cli import (
    format_output,
    load_test_definitions,
    log_results_summary,
    run,
)
from scan_test_action.models.result import TestResult
from scan_test_action.orchestrator import ScannerResult
from scan_test_action.testing.github.factories import TestDefinitionFactory


def test_log_results_summary_success(caplog: pytest.LogCaptureFixture) -> None:
    """Logs success results with checkmark symbol."""
    scanner_results = [
        ScannerResult(
            scanner_id="org/scanner",
            results=[
                TestResult(
                    status="success",
                    duration=10.5,
                    run_url="https://example.com/run/123",
                )
            ],
        )
    ]

    with caplog.at_level(logging.INFO):
        log_results_summary(logging.getLogger(), scanner_results)

    assert "Test Results Summary:" in caplog.text
    assert "✓ org/scanner: success (10.50s)" in caplog.text
    assert "Run URL: https://example.com/run/123" in caplog.text


def test_log_results_summary_failure(caplog: pytest.LogCaptureFixture) -> None:
    """Logs failure results with X symbol."""
    scanner_results = [
        ScannerResult(
            scanner_id="org/scanner",
            results=[
                TestResult(
                    status="failure",
                    duration=5.0,
                    run_url="https://example.com/run/456",
                )
            ],
        )
    ]

    with caplog.at_level(logging.INFO):
        log_results_summary(logging.getLogger(), scanner_results)

    assert "✗ org/scanner: failure (5.00s)" in caplog.text
    assert "Run URL: https://example.com/run/456" in caplog.text


def test_log_results_summary_with_message(caplog: pytest.LogCaptureFixture) -> None:
    """Logs error message when present."""
    scanner_results = [
        ScannerResult(
            scanner_id="org/scanner",
            results=[
                TestResult(
                    status="error",
                    duration=0.0,
                    message="API connection failed",
                )
            ],
        )
    ]

    with caplog.at_level(logging.INFO):
        log_results_summary(logging.getLogger(), scanner_results)

    assert "! org/scanner: error (0.00s)" in caplog.text
    assert "Message: API connection failed" in caplog.text


def test_log_results_summary_timeout(caplog: pytest.LogCaptureFixture) -> None:
    """Logs timeout results with timer symbol."""
    scanner_results = [
        ScannerResult(
            scanner_id="org/scanner",
            results=[
                TestResult(
                    status="timeout",
                    duration=600.0,
                    run_url="https://example.com/run/789",
                )
            ],
        )
    ]

    with caplog.at_level(logging.INFO):
        log_results_summary(logging.getLogger(), scanner_results)

    assert "⏱ org/scanner: timeout (600.00s)" in caplog.text


def test_log_results_summary_multiple_scanners(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Logs results for multiple scanners."""
    scanner_results = [
        ScannerResult(
            scanner_id="org/scanner1",
            results=[
                TestResult(
                    status="success",
                    duration=10.0,
                    run_url="https://example.com/run/1",
                )
            ],
        ),
        ScannerResult(
            scanner_id="org/scanner2",
            results=[
                TestResult(
                    status="failure",
                    duration=20.0,
                    run_url="https://example.com/run/2",
                )
            ],
        ),
    ]

    with caplog.at_level(logging.INFO):
        log_results_summary(logging.getLogger(), scanner_results)

    assert "✓ org/scanner1: success (10.00s)" in caplog.text
    assert "https://example.com/run/1" in caplog.text
    assert "✗ org/scanner2: failure (20.00s)" in caplog.text
    assert "https://example.com/run/2" in caplog.text


def test_format_output_empty() -> None:
    """Returns empty totals when no results."""
    output = format_output([])

    assert output == {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "timeouts": 0,
        "results": [],
    }


def test_format_output_single_success() -> None:
    """Formats single success result correctly."""
    scanner_results = [
        ScannerResult(
            scanner_id="org/scanner",
            results=[
                TestResult(
                    status="success",
                    duration=10.5,
                    run_url="https://example.com/run/123",
                )
            ],
        )
    ]

    output = format_output(scanner_results)

    assert output["total"] == 1
    assert output["passed"] == 1
    assert output["failed"] == 0
    assert len(output["results"]) == 1
    assert output["results"][0]["scanner"] == "org/scanner"
    assert output["results"][0]["status"] == "success"
    assert output["results"][0]["duration"] == 10.5
    assert output["results"][0]["run_url"] == "https://example.com/run/123"


def test_format_output_mixed_results() -> None:
    """Formats mixed results with correct totals."""
    scanner_results = [
        ScannerResult(
            scanner_id="org/scanner1",
            results=[TestResult(status="success", duration=10.0)],
        ),
        ScannerResult(
            scanner_id="org/scanner2",
            results=[TestResult(status="failure", duration=20.0)],
        ),
        ScannerResult(
            scanner_id="org/scanner3",
            results=[TestResult(status="error", duration=0.0, message="API Error")],
        ),
        ScannerResult(
            scanner_id="org/scanner4",
            results=[TestResult(status="timeout", duration=600.0)],
        ),
    ]

    output = format_output(scanner_results)

    assert output["total"] == 4
    assert output["passed"] == 1
    assert output["failed"] == 1
    assert output["errors"] == 1
    assert output["timeouts"] == 1


class TestLoadTestDefinitions:
    """Tests for load_test_definitions function."""

    async def test_loads_definitions_for_scanners(self) -> None:
        """Loads test definitions for given scanner IDs."""
        test_def = TestDefinitionFactory.build()

        with patch(
            "scan_test_action.cli.load_test_definition",
            new_callable=AsyncMock,
            return_value=test_def,
        ) as mock_load:
            result = await load_test_definitions(Path("/registry"), ["org/scanner"])

        assert "org/scanner" in result
        assert result["org/scanner"] == test_def
        mock_load.assert_called_once_with(Path("/registry"), "org/scanner")

    async def test_skips_missing_definitions(self) -> None:
        """Skips scanners without test definitions."""
        with patch(
            "scan_test_action.cli.load_test_definition",
            new_callable=AsyncMock,
            side_effect=FileNotFoundError,
        ):
            result = await load_test_definitions(Path("/registry"), ["org/scanner"])

        assert result == {}


class TestRun:
    """Tests for run function."""

    @pytest.fixture
    def mock_provider(self) -> Mock:
        """Create mock provider."""
        provider = Mock()
        provider.run_tests = AsyncMock(return_value=[])
        return provider

    @pytest.fixture
    def mock_context_manager(self, mock_provider: Mock) -> AsyncMock:
        """Create mock async context manager that yields provider."""
        cm = AsyncMock()
        cm.__aenter__.return_value = mock_provider
        cm.__aexit__.return_value = None
        return cm

    async def test_returns_zero_when_no_changed_scanners(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Returns 0 and prints empty results when no scanners changed."""
        with (
            patch("scan_test_action.cli.load_provider_manifest") as mock_load_manifest,
            patch(
                "scan_test_action.cli.get_scanners_to_test",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            mock_manifest = Mock()
            mock_manifest.config_cls = Mock(return_value=Mock())
            mock_load_manifest.return_value = mock_manifest

            exit_code = await run(
                provider_key="github-actions",
                provider_config_json='{"token": "test"}',
                registry_path=Path("/registry"),
                registry_repo="org/registry",
                registry_ref="abc123",
                base_ref="main",
            )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert '"total": 0' in captured.out

    async def test_returns_zero_when_no_test_definitions(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Returns 0 when changed scanners have no test definitions."""
        with (
            patch("scan_test_action.cli.load_provider_manifest") as mock_load_manifest,
            patch(
                "scan_test_action.cli.get_scanners_to_test",
                new_callable=AsyncMock,
                return_value=["org/scanner"],
            ),
            patch(
                "scan_test_action.cli.load_test_definition",
                new_callable=AsyncMock,
                side_effect=FileNotFoundError,
            ),
        ):
            mock_manifest = Mock()
            mock_manifest.config_cls = Mock(return_value=Mock())
            mock_load_manifest.return_value = mock_manifest

            exit_code = await run(
                provider_key="github-actions",
                provider_config_json='{"token": "test"}',
                registry_path=Path("/registry"),
                registry_repo="org/registry",
                registry_ref="abc123",
                base_ref="main",
            )

        assert exit_code == 0

    async def test_returns_zero_when_all_tests_pass(
        self,
        mock_context_manager: AsyncMock,
        mock_provider: Mock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Returns 0 when all tests pass."""
        test_def = TestDefinitionFactory.build()

        with (
            patch("scan_test_action.cli.load_provider_manifest") as mock_load_manifest,
            patch(
                "scan_test_action.cli.get_scanners_to_test",
                new_callable=AsyncMock,
                return_value=["org/scanner"],
            ),
            patch(
                "scan_test_action.cli.load_test_definition",
                new_callable=AsyncMock,
                return_value=test_def,
            ),
            patch("scan_test_action.cli.TestOrchestrator") as mock_orchestrator_cls,
        ):
            mock_manifest = Mock()
            mock_manifest.config_cls = Mock(return_value=Mock())
            mock_manifest.provider_factory = Mock(return_value=mock_context_manager)
            mock_load_manifest.return_value = mock_manifest

            mock_orchestrator = Mock()
            mock_orchestrator.run_tests = AsyncMock(
                return_value=[
                    ScannerResult(
                        scanner_id="org/scanner",
                        results=[TestResult(status="success", duration=10.0)],
                    )
                ]
            )
            mock_orchestrator_cls.return_value = mock_orchestrator

            exit_code = await run(
                provider_key="github-actions",
                provider_config_json='{"token": "test"}',
                registry_path=Path("/registry"),
                registry_repo="org/registry",
                registry_ref="abc123",
                base_ref="main",
            )

        assert exit_code == 0
        captured = capsys.readouterr()
        assert '"passed": 1' in captured.out

    async def test_returns_one_when_test_fails(
        self,
        mock_context_manager: AsyncMock,
        mock_provider: Mock,
    ) -> None:
        """Returns 1 when any test fails."""
        test_def = TestDefinitionFactory.build()

        with (
            patch("scan_test_action.cli.load_provider_manifest") as mock_load_manifest,
            patch(
                "scan_test_action.cli.get_scanners_to_test",
                new_callable=AsyncMock,
                return_value=["org/scanner"],
            ),
            patch(
                "scan_test_action.cli.load_test_definition",
                new_callable=AsyncMock,
                return_value=test_def,
            ),
            patch("scan_test_action.cli.TestOrchestrator") as mock_orchestrator_cls,
        ):
            mock_manifest = Mock()
            mock_manifest.config_cls = Mock(return_value=Mock())
            mock_manifest.provider_factory = Mock(return_value=mock_context_manager)
            mock_load_manifest.return_value = mock_manifest

            mock_orchestrator = Mock()
            mock_orchestrator.run_tests = AsyncMock(
                return_value=[
                    ScannerResult(
                        scanner_id="org/scanner",
                        results=[TestResult(status="failure", duration=10.0)],
                    )
                ]
            )
            mock_orchestrator_cls.return_value = mock_orchestrator

            exit_code = await run(
                provider_key="github-actions",
                provider_config_json='{"token": "test"}',
                registry_path=Path("/registry"),
                registry_repo="org/registry",
                registry_ref="abc123",
                base_ref="main",
            )

        assert exit_code == 1

    async def test_returns_one_when_test_errors(
        self,
        mock_context_manager: AsyncMock,
        mock_provider: Mock,
    ) -> None:
        """Returns 1 when any test errors."""
        test_def = TestDefinitionFactory.build()

        with (
            patch("scan_test_action.cli.load_provider_manifest") as mock_load_manifest,
            patch(
                "scan_test_action.cli.get_scanners_to_test",
                new_callable=AsyncMock,
                return_value=["org/scanner"],
            ),
            patch(
                "scan_test_action.cli.load_test_definition",
                new_callable=AsyncMock,
                return_value=test_def,
            ),
            patch("scan_test_action.cli.TestOrchestrator") as mock_orchestrator_cls,
        ):
            mock_manifest = Mock()
            mock_manifest.config_cls = Mock(return_value=Mock())
            mock_manifest.provider_factory = Mock(return_value=mock_context_manager)
            mock_load_manifest.return_value = mock_manifest

            mock_orchestrator = Mock()
            mock_orchestrator.run_tests = AsyncMock(
                return_value=[
                    ScannerResult(
                        scanner_id="org/scanner",
                        results=[TestResult(status="error", duration=0.0)],
                    )
                ]
            )
            mock_orchestrator_cls.return_value = mock_orchestrator

            exit_code = await run(
                provider_key="github-actions",
                provider_config_json='{"token": "test"}',
                registry_path=Path("/registry"),
                registry_repo="org/registry",
                registry_ref="abc123",
                base_ref="main",
            )

        assert exit_code == 1

    async def test_returns_one_when_test_times_out(
        self,
        mock_context_manager: AsyncMock,
        mock_provider: Mock,
    ) -> None:
        """Returns 1 when any test times out."""
        test_def = TestDefinitionFactory.build()

        with (
            patch("scan_test_action.cli.load_provider_manifest") as mock_load_manifest,
            patch(
                "scan_test_action.cli.get_scanners_to_test",
                new_callable=AsyncMock,
                return_value=["org/scanner"],
            ),
            patch(
                "scan_test_action.cli.load_test_definition",
                new_callable=AsyncMock,
                return_value=test_def,
            ),
            patch("scan_test_action.cli.TestOrchestrator") as mock_orchestrator_cls,
        ):
            mock_manifest = Mock()
            mock_manifest.config_cls = Mock(return_value=Mock())
            mock_manifest.provider_factory = Mock(return_value=mock_context_manager)
            mock_load_manifest.return_value = mock_manifest

            mock_orchestrator = Mock()
            mock_orchestrator.run_tests = AsyncMock(
                return_value=[
                    ScannerResult(
                        scanner_id="org/scanner",
                        results=[TestResult(status="timeout", duration=600.0)],
                    )
                ]
            )
            mock_orchestrator_cls.return_value = mock_orchestrator

            exit_code = await run(
                provider_key="github-actions",
                provider_config_json='{"token": "test"}',
                registry_path=Path("/registry"),
                registry_repo="org/registry",
                registry_ref="abc123",
                base_ref="main",
            )

        assert exit_code == 1


class TestMain:
    """Tests for main CLI entry point."""

    def test_exits_with_run_result(self) -> None:
        """Main function exits with the result from run()."""
        from scan_test_action.cli import main

        with (
            patch(
                "sys.argv",
                [
                    "cli",
                    "--provider",
                    "github-actions",
                    "--provider-config",
                    '{"token": "test"}',
                    "--registry-path",
                    "/registry",
                    "--registry-repo",
                    "org/registry",
                    "--registry-ref",
                    "abc123",
                    "--base-ref",
                    "main",
                ],
            ),
            patch("scan_test_action.cli.asyncio.run", return_value=0) as mock_run,
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 0
        mock_run.assert_called_once()

    def test_exits_with_failure_code(self) -> None:
        """Main function exits with code 1 on test failures."""
        from scan_test_action.cli import main

        with (
            patch(
                "sys.argv",
                [
                    "cli",
                    "--provider",
                    "github-actions",
                    "--provider-config",
                    '{"token": "test"}',
                    "--registry-path",
                    "/registry",
                    "--registry-repo",
                    "org/registry",
                    "--registry-ref",
                    "abc123",
                    "--base-ref",
                    "main",
                ],
            ),
            patch("scan_test_action.cli.asyncio.run", return_value=1),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()

        assert exc_info.value.code == 1

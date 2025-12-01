"""Fixtures for module tests using WireMock testcontainers."""

import subprocess
from collections.abc import Generator
from pathlib import Path

import pytest
from testcontainers.core import testcontainers_config
from testcontainers.core.network import Network
from wiremock.constants import Config
from wiremock.testing.testcontainer import WireMockContainer


@pytest.fixture(scope="session", autouse=True)
def _disable_ryuk() -> None:
    """Disable the extra cleanup instance, we use contexts to clean containers."""
    testcontainers_config.ryuk_disabled = True


@pytest.fixture(scope="session")
def docker_network() -> Generator[Network]:
    """Create a Docker network for WireMock and act to communicate."""
    with Network() as network:
        yield network


@pytest.fixture(scope="session")
def wiremock_server_name() -> str:
    """Define a name for the container in the docker DNS."""
    return "wiremock"


@pytest.fixture(scope="session")
def wiremock_server(
    docker_network: Network, wiremock_server_name: str
) -> Generator[WireMockContainer, None, None]:
    """Start WireMock container using wiremock's testcontainer support."""
    container = (
        WireMockContainer(secure=False)
        .with_network(docker_network)
        .with_name("wiremock")
    )

    with container as wm:
        Config.base_url = wm.get_url("__admin")
        yield wm
        print(wm.get_logs())


@pytest.fixture(scope="session")
def wiremock_url(wiremock_server_name: str) -> str:
    """URL for WireMock from inside the Docker network."""
    return f"http://{wiremock_server_name}:8080"


@pytest.fixture(scope="session")
def registry_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a scanner registry with test data."""
    registry = tmp_path_factory.mktemp("registry")

    subprocess.run(
        ["git", "init"],
        cwd=registry,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=registry,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=registry,
        check=True,
        capture_output=True,
    )

    return registry


@pytest.fixture(scope="session")
def base_commit(registry_path: Path) -> str:
    """Create initial commit (base ref for comparison)."""
    readme = registry_path / "README.md"
    readme.write_text("# Scanner Registry\n")

    subprocess.run(
        ["git", "add", "-A"],
        cwd=registry_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=registry_path,
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=registry_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture(scope="session")
def head_commit(registry_path: Path, base_commit: str) -> str:
    """Create scanner with test definition and return head commit."""
    scanner_dir = registry_path / "scanners" / "test-org" / "test-scanner"
    scanner_dir.mkdir(parents=True, exist_ok=True)

    (scanner_dir / "module.yaml").write_text("name: test-scanner\n")
    (scanner_dir / "tests.yaml").write_text("""version: '1.0'
tests:
  - name: smoke-test
    type: source-code
    source:
      url: https://github.com/test/repo.git
      ref: main
    scan_paths:
      - "."
""")

    subprocess.run(
        ["git", "add", "-A"],
        cwd=registry_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Add test scanner"],
        cwd=registry_path,
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=registry_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()

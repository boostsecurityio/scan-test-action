"""Module test for GitHub Actions provider using WireMock and act."""

import json
import subprocess
from pathlib import Path

from testcontainers.core.network import Network
from wiremock.client import (
    HttpMethods,
    Mapping,
    MappingRequest,
    MappingResponse,
    Mappings,
)
from wiremock.testing.testcontainer import WireMockContainer

from scan_test_action.testing.github.payloads import (
    workflow_run,
    workflow_runs_response,
)


def test_action_with_github_actions_provider(
    registry_path: Path,
    base_commit: str,
    head_commit: str,
    wiremock_server: WireMockContainer,
    wiremock_url: str,
    docker_network: Network,
) -> None:
    """Action dispatches and polls GitHub Actions workflow via provider."""
    # Clear any existing mappings
    Mappings.delete_all_mappings()

    # Mock workflow dispatch (POST)
    Mappings.create_mapping(
        Mapping(
            request=MappingRequest(
                method=HttpMethods.POST,
                url_path_pattern="/repos/.*/actions/workflows/.*/dispatches",
            ),
            response=MappingResponse(
                status=204,
                headers={"Content-Type": "application/json"},
            ),
        )
    )

    # Mock workflow runs list (GET) - returns completed run with static dispatch_id
    Mappings.create_mapping(
        Mapping(
            request=MappingRequest(
                method=HttpMethods.GET,
                url_path_pattern="/repos/.*/actions/runs.*",
            ),
            response=MappingResponse(
                status=200,
                headers={"Content-Type": "application/json"},
                json_body=workflow_runs_response(
                    workflow_runs=[
                        workflow_run(
                            run_id=123,
                            display_title="[static-dispatch-id]",
                            status="completed",
                            conclusion="success",
                            html_url="https://github.com/test/runs/123",
                            created_at="2099-01-01T12:00:00Z",
                            updated_at="2099-01-01T12:01:30Z",
                        )
                    ]
                ),
            ),
        )
    )

    # Create a test workflow that uses the action
    workflows_dir = registry_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    action_path = Path(__file__).parent.parent.parent.resolve()

    provider_config = json.dumps(
        {
            "token": "test-token",
            "owner": "test-owner",
            "repo": "test-repo",
            "workflow_id": "test.yml",
            "api_base_url": wiremock_url,
            "dispatch_id_mode": "static",
        }
    )

    # Use a fake action reference that we'll map to the local action path
    workflow_content = f"""name: Test Scanner
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: test-action/scan-test-action@main
        with:
          provider: github-actions
          provider-config: '{provider_config}'
          registry-path: '.'
          registry-repo: 'test-org/scanner-registry'
          base-ref: '{base_commit}'
"""

    (workflows_dir / "test.yml").write_text(workflow_content)

    # Commit the workflow
    subprocess.run(
        ["git", "add", "-A"],
        cwd=registry_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Add test workflow"],
        cwd=registry_path,
        check=True,
        capture_output=True,
    )

    # Run act with the docker network and map local action
    result = subprocess.run(
        [
            "act",
            "push",
            "--network",
            docker_network.name,
            "-j",
            "test",
            "--env",
            f"GITHUB_SHA={head_commit}",
            "-P",
            "ubuntu-latest=catthehacker/ubuntu:act-latest",
            "--container-architecture",
            "linux/amd64",
            "--local-repository",
            f"test-action/scan-test-action@main={action_path}",
        ],
        cwd=registry_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"act failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Verify test results in output
    assert '"total": 1' in result.stdout, f"Expected 1 test result:\n{result.stdout}"
    assert '"passed": 1' in result.stdout, f"Expected 1 passed test:\n{result.stdout}"
    assert '"status": "success"' in result.stdout, (
        f"Expected success status:\n{result.stdout}"
    )


def test_fallback_scanners_triggered_on_workflow_change(
    registry_path: Path,
    base_commit: str,
    head_commit: str,
    wiremock_server: WireMockContainer,
    wiremock_url: str,
    docker_network: Network,
) -> None:
    """Fallback scanners are tested when only workflow files change."""
    # Clear any existing mappings
    Mappings.delete_all_mappings()

    # Mock workflow dispatch (POST)
    Mappings.create_mapping(
        Mapping(
            request=MappingRequest(
                method=HttpMethods.POST,
                url_path_pattern="/repos/.*/actions/workflows/.*/dispatches",
            ),
            response=MappingResponse(
                status=204,
                headers={"Content-Type": "application/json"},
            ),
        )
    )

    # Mock workflow runs list (GET) - returns completed run with static dispatch_id
    Mappings.create_mapping(
        Mapping(
            request=MappingRequest(
                method=HttpMethods.GET,
                url_path_pattern="/repos/.*/actions/runs.*",
            ),
            response=MappingResponse(
                status=200,
                headers={"Content-Type": "application/json"},
                json_body=workflow_runs_response(
                    workflow_runs=[
                        workflow_run(
                            run_id=456,
                            display_title="[static-dispatch-id]",
                            status="completed",
                            conclusion="success",
                            html_url="https://github.com/test/runs/456",
                            created_at="2099-01-01T12:00:00Z",
                            updated_at="2099-01-01T12:01:30Z",
                        )
                    ]
                ),
            ),
        )
    )

    # Get current HEAD as base for this test
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=registry_path,
        check=True,
        capture_output=True,
        text=True,
    )
    test_base_commit = result.stdout.strip()

    # Create/modify workflow file only (no scanner changes)
    workflows_dir = registry_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    action_path = Path(__file__).parent.parent.parent.resolve()

    # Use the existing test scanner as a fallback
    fallback_scanner = "test-org/test-scanner"

    provider_config = json.dumps(
        {
            "token": "test-token",
            "owner": "test-owner",
            "repo": "test-repo",
            "workflow_id": "test.yml",
            "api_base_url": wiremock_url,
            "dispatch_id_mode": "static",
        }
    )

    workflow_content = f"""name: Test Scanner Fallback
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: test-action/scan-test-action@main
        with:
          provider: github-actions
          provider-config: '{provider_config}'
          registry-path: '.'
          registry-repo: 'test-org/scanner-registry'
          base-ref: '{test_base_commit}'
          fallback-scanners: '{fallback_scanner}'
"""

    (workflows_dir / "fallback-test.yml").write_text(workflow_content)

    # Commit the workflow change
    subprocess.run(
        ["git", "add", "-A"],
        cwd=registry_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "Add fallback test workflow"],
        cwd=registry_path,
        check=True,
        capture_output=True,
    )

    # Get the new HEAD commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=registry_path,
        check=True,
        capture_output=True,
        text=True,
    )
    new_head_commit = result.stdout.strip()

    # Run act with the docker network and map local action
    result = subprocess.run(
        [
            "act",
            "push",
            "--network",
            docker_network.name,
            "-j",
            "test",
            "-W",
            ".github/workflows/fallback-test.yml",
            "--env",
            f"GITHUB_SHA={new_head_commit}",
            "-P",
            "ubuntu-latest=catthehacker/ubuntu:act-latest",
            "--container-architecture",
            "linux/amd64",
            "--local-repository",
            f"test-action/scan-test-action@main={action_path}",
        ],
        cwd=registry_path,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"act failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Verify fallback scanner was tested
    assert '"total": 1' in result.stdout, f"Expected 1 test result:\n{result.stdout}"
    assert '"passed": 1' in result.stdout, f"Expected 1 passed test:\n{result.stdout}"
    assert '"status": "success"' in result.stdout, (
        f"Expected success status:\n{result.stdout}"
    )

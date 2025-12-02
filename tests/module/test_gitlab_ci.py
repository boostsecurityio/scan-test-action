"""Module test for GitLab CI provider using WireMock and act."""

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

from scan_test_action.testing.gitlab.payloads import create_pipeline_response, pipeline


def test_action_with_gitlab_ci_provider(
    registry_path: Path,
    base_commit: str,
    head_commit: str,
    wiremock_server: WireMockContainer,
    wiremock_url: str,
    docker_network: Network,
) -> None:
    """Action dispatches and polls GitLab CI pipeline via provider."""
    # Clear any existing mappings
    Mappings.delete_all_mappings()

    # Mock pipeline dispatch (POST)
    Mappings.create_mapping(
        Mapping(
            request=MappingRequest(
                method=HttpMethods.POST,
                url_path_pattern="/api/v4/projects/.*/pipeline",
            ),
            response=MappingResponse(
                status=201,
                headers={"Content-Type": "application/json"},
                json_body=create_pipeline_response(pipeline_id=789),
            ),
        )
    )

    # Mock pipeline status (GET) - returns completed pipeline
    Mappings.create_mapping(
        Mapping(
            request=MappingRequest(
                method=HttpMethods.GET,
                url_path_pattern="/api/v4/projects/.*/pipelines/.*",
            ),
            response=MappingResponse(
                status=200,
                headers={"Content-Type": "application/json"},
                json_body=pipeline(
                    pipeline_id=789,
                    status="success",
                    web_url="https://gitlab.com/test/project/-/pipelines/789",
                    created_at="2099-01-01T12:00:00Z",
                    updated_at="2099-01-01T12:01:30Z",
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
            "token": "glpat-test-token",
            "project_id": "test-group/test-project",
            "api_base_url": f"{wiremock_url}/api/v4/",
        }
    )

    workflow_content = f"""name: Test Scanner
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: test-action/scan-test-action@main
        with:
          provider: gitlab-ci
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

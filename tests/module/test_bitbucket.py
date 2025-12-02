"""Module test for Bitbucket Pipelines provider using WireMock and act."""

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

from scan_test_action.testing.bitbucket.payloads import (
    create_pipeline_response,
    pipeline,
)


def test_action_with_bitbucket_provider(
    registry_path: Path,
    base_commit: str,
    head_commit: str,
    wiremock_server: WireMockContainer,
    wiremock_url: str,
    docker_network: Network,
) -> None:
    """Action dispatches and polls Bitbucket pipeline via provider."""
    # Clear any existing mappings
    Mappings.delete_all_mappings()

    run_url = "https://bitbucket.org/test-workspace/test-repo/pipelines/results/42"

    # Mock pipeline dispatch (POST)
    Mappings.create_mapping(
        Mapping(
            request=MappingRequest(
                method=HttpMethods.POST,
                url_path_pattern="/2.0/repositories/.*/pipelines/",
            ),
            response=MappingResponse(
                status=201,
                headers={
                    "Content-Type": "application/json",
                    "Location": run_url,
                },
                json_body=create_pipeline_response(uuid="{abc-123-def}"),
            ),
        )
    )

    # Mock pipeline status (GET) - returns completed pipeline
    Mappings.create_mapping(
        Mapping(
            request=MappingRequest(
                method=HttpMethods.GET,
                url_path_pattern="/2.0/repositories/.*/pipelines/.*",
            ),
            response=MappingResponse(
                status=200,
                headers={"Content-Type": "application/json"},
                json_body=pipeline(
                    uuid="{abc-123-def}",
                    state_name="COMPLETED",
                    result_name="SUCCESSFUL",
                    created_on="2099-01-01T12:00:00.000000+00:00",
                    completed_on="2099-01-01T12:01:30.000000+00:00",
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
            "token": "test-oauth-token",
            "workspace": "test-workspace",
            "repo_slug": "test-repo",
            "api_base_url": f"{wiremock_url}/2.0/",
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
          provider: bitbucket
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

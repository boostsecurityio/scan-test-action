"""Payload helpers for Bitbucket Pipelines API responses in tests."""

from typing import Any


def pipeline(
    *,
    uuid: str = "{abc-123-def}",
    build_number: int = 42,
    state_name: str = "COMPLETED",
    result_name: str | None = "SUCCESSFUL",
    created_on: str = "2099-01-01T12:00:00.000000+00:00",
    completed_on: str | None = "2099-01-01T12:01:00.000000+00:00",
) -> dict[str, Any]:
    """Create a pipeline payload for testing.

    Returns a realistic Bitbucket pipeline API response structure.
    """
    state: dict[str, Any] = {"name": state_name}
    if result_name is not None:
        state["result"] = {"name": result_name}

    payload: dict[str, Any] = {
        "uuid": uuid,
        "build_number": build_number,
        "state": state,
        "created_on": created_on,
        "repository": {
            "uuid": "{repo-uuid}",
            "name": "test-repo",
            "full_name": "test-workspace/test-repo",
        },
        "target": {
            "type": "pipeline_ref_target",
            "ref_name": "main",
            "ref_type": "branch",
        },
    }

    if completed_on is not None:
        payload["completed_on"] = completed_on

    return payload


def create_pipeline_response(
    *,
    uuid: str = "{abc-123-def}",
) -> dict[str, Any]:
    """Create a pipeline creation response payload.

    This is the response from POST /repositories/{workspace}/{repo}/pipelines/.
    """
    return {
        "uuid": uuid,
        "state": {"name": "PENDING"},
        "created_on": "2099-01-01T12:00:00.000000+00:00",
        "repository": {
            "uuid": "{repo-uuid}",
            "name": "test-repo",
            "full_name": "test-workspace/test-repo",
        },
    }

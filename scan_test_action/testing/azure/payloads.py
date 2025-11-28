"""Payload helpers for Azure DevOps API responses in tests."""

from typing import Any


def pipeline_run(
    *,
    run_id: int = 12345,
    name: str = "Scanner Test Pipeline",
    state: str = "completed",
    result: str | None = "succeeded",
    created_date: str = "2099-01-01T12:00:00Z",
    finished_date: str | None = "2099-01-01T12:01:00Z",
    web_url: str = "https://dev.azure.com/test-org/test-project/_build/results?buildId=12345",
) -> dict[str, Any]:
    """Create a pipeline run payload for testing.

    Returns a realistic Azure DevOps pipeline run API response structure.
    """
    payload: dict[str, Any] = {
        "id": run_id,
        "name": name,
        "state": state,
        "createdDate": created_date,
        "pipeline": {
            "id": 42,
            "name": "scanner-test",
            "folder": "\\",
            "revision": 1,
        },
        "_links": {
            "self": {
                "href": f"https://dev.azure.com/test-org/test-project/_apis/pipelines/42/runs/{run_id}"
            },
            "web": {"href": web_url},
        },
    }

    if result is not None:
        payload["result"] = result

    if finished_date is not None:
        payload["finishedDate"] = finished_date

    return payload


def create_run_response(
    *,
    run_id: int = 12345,
    web_url: str = "https://dev.azure.com/test-org/test-project/_build/results?buildId=12345",
) -> dict[str, Any]:
    """Create a pipeline run creation response payload.

    This is the response from POST /_apis/pipelines/{id}/runs.
    """
    return {
        "id": run_id,
        "name": "20991231.1",
        "state": "inProgress",
        "createdDate": "2099-01-01T12:00:00Z",
        "pipeline": {
            "id": 42,
            "name": "scanner-test",
            "folder": "\\",
            "revision": 1,
        },
        "_links": {
            "self": {
                "href": f"https://dev.azure.com/test-org/test-project/_apis/pipelines/42/runs/{run_id}"
            },
            "web": {"href": web_url},
        },
    }

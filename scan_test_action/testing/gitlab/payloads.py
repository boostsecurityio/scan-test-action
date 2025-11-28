"""Payload helpers for GitLab CI API responses in tests."""

from typing import Any


def pipeline(
    *,
    pipeline_id: int = 123456789,
    status: str = "success",
    ref: str = "main",
    web_url: str = "https://gitlab.com/test/project/-/pipelines/123456789",
    created_at: str = "2099-01-01T12:00:00Z",
    updated_at: str = "2099-01-01T12:01:00Z",
) -> dict[str, Any]:
    """Create a pipeline payload for testing.

    Returns a realistic GitLab pipeline API response structure.
    """
    return {
        "id": pipeline_id,
        "iid": 42,
        "project_id": 12345,
        "sha": "abc123def456",
        "ref": ref,
        "status": status,
        "source": "api",
        "created_at": created_at,
        "updated_at": updated_at,
        "web_url": web_url,
        "before_sha": "0000000000000000000000000000000000000000",
        "tag": False,
        "yaml_errors": None,
        "user": {
            "id": 1,
            "username": "test-user",
            "name": "Test User",
            "state": "active",
            "avatar_url": "https://gitlab.com/uploads/-/system/user/avatar/1/avatar.png",
            "web_url": "https://gitlab.com/test-user",
        },
        "started_at": created_at,
        "finished_at": updated_at,
        "committed_at": None,
        "duration": 60,
        "queued_duration": 1,
        "coverage": None,
        "detailed_status": {
            "icon": "status_success",
            "text": "passed",
            "label": "passed",
            "group": "success",
            "tooltip": "passed",
            "has_details": True,
            "details_path": f"/test/project/-/pipelines/{pipeline_id}",
            "illustration": None,
            "favicon": "/assets/ci_favicons/favicon_status_success.png",
        },
    }


def create_pipeline_response(
    *,
    pipeline_id: int = 123456789,
    web_url: str = "https://gitlab.com/test/project/-/pipelines/123456789",
) -> dict[str, Any]:
    """Create a pipeline creation response payload.

    This is the response from POST /projects/:id/pipeline.
    """
    return {
        "id": pipeline_id,
        "iid": 42,
        "project_id": 12345,
        "sha": "abc123def456",
        "ref": "main",
        "status": "created",
        "source": "api",
        "created_at": "2099-01-01T12:00:00Z",
        "updated_at": "2099-01-01T12:00:00Z",
        "web_url": web_url,
    }

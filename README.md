# Scan Test Action

A GitHub Action for running automated tests when scanners are modified in the scanner registry.

## Overview

This action detects which scanners have been modified in a pull request and runs their associated tests across CI/CD providers. It enables scanner authors to validate their changes before merging.

## Scanner Detection

The action compares the PR branch against the base branch to identify modified scanners. A scanner is considered modified if any file under `scanners/<org>/<scanner>/` has changed.

Only scanners with a `tests.yaml` file are tested. Scanners without test definitions are skipped.

### How It Works

1. Compares git refs (e.g., `origin/main` vs `HEAD`) to find changed files
2. Extracts unique scanner identifiers from paths like `scanners/org/scanner/file.yaml`
3. Filters to only scanners that have a `tests.yaml` file
4. Returns the list of testable scanners

### Git Reference Resolution

In CI environments like GitHub Actions, branch refs often exist with an `origin/` prefix. The detector automatically tries both forms when resolving references.

## Test Definition Format

Scanner tests are defined in `tests.yaml` files within each scanner directory:

```yaml
version: "1.0"
tests:
  - name: "Smoke test - source code"
    type: "source-code"
    source:
      url: "https://github.com/OWASP/NodeGoat.git"
      ref: "main"

  - name: "Container image scan"
    type: "container-image"
    source:
      url: "https://github.com/example/docker-app.git"
      ref: "v1.0"
    scan_paths:
      - "app"
      - "api"
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| `version` | Yes | Schema version (currently "1.0") |
| `tests` | Yes | List of test specifications |
| `tests[].name` | Yes | Human-readable test name |
| `tests[].type` | Yes | Either "source-code" or "container-image" |
| `tests[].source.url` | Yes | Git repository URL (HTTPS) |
| `tests[].source.ref` | Yes | Git reference (branch, tag, or commit SHA) |
| `tests[].scan_paths` | No | Paths to scan (default: ["."]) |
| `tests[].timeout` | No | Test timeout (default: "5m") |

### Matrix Expansion

Each test is expanded into matrix entries for CI execution. A test with multiple `scan_paths` creates one matrix entry per path, enabling parallel execution.

## Provider Architecture

The action supports multiple CI/CD providers through a common interface. Each provider handles dispatching tests and polling for results.

### Provider Interface

Providers implement `PipelineProvider[T]`, a generic interface where `T` is the dispatch state type:

```python
@dataclass(frozen=True, kw_only=True)
class MyProvider(PipelineProvider[str]):
    # Configuration fields...

    async def dispatch_scanner_tests(...) -> str:
        # Dispatch tests, return state for polling
        return run_id

    async def poll_status(dispatch_state: str) -> Sequence[TestResult] | None:
        # Return results when complete, None when still running
        return results if complete else None
```

The generic type allows providers to pass any state between dispatch and poll - from a simple run ID to complex objects with multiple identifiers.

### Wait Logic

The base class provides `wait_for_completion()` which handles polling with timeout. Providers only implement the dispatch and poll methods.

## GitHub Actions Provider

The `GitHubActionsProvider` dispatches tests to a GitHub Actions workflow and polls for completion.

### Configuration

When calling this action from a GitHub workflow, the provider configuration is passed as a JSON object:

```yaml
- uses: boostsecurityio/scanner-registry-testing/test-action@main
  with:
    provider: github-actions
    provider-config: |
      {
        "token": "${{ secrets.TEST_RUNNER_TOKEN }}",
        "owner": "boostsecurityio",
        "repo": "test-runner-github",
        "workflow_id": "scanner-test.yml",
        "ref": "main"
      }
```

| Field | Required | Description |
|-------|----------|-------------|
| `token` | Yes | GitHub token with workflow permissions |
| `owner` | Yes | Repository owner |
| `repo` | Yes | Repository name |
| `workflow_id` | Yes | Workflow file name or ID |
| `ref` | No | Branch to run workflow on (default: "main") |

### Dispatch ID for Deterministic Matching

The provider generates a unique dispatch ID (UUID) for each workflow dispatch. This ID is passed as a workflow input and should be displayed in the workflow's `run-name`. The provider uses this ID to reliably find the correct workflow run among concurrent executions.

**Test runner workflow requirements:**
- Accept `dispatch_id` as a workflow input
- Include the dispatch ID in `run-name` (e.g., `run-name: "[${{ inputs.dispatch_id }}] Scanner Tests"`)

### Session Management

The provider uses a single `aiohttp.ClientSession` for its lifetime, configured with the base URL and authorization headers. Use the `from_config` async context manager to ensure proper cleanup.

## GitLab CI Provider

The `GitLabCIProvider` dispatches tests to a GitLab CI pipeline and polls for completion.

### Configuration

```yaml
- uses: boostsecurityio/scanner-registry-testing/test-action@main
  with:
    provider: gitlab-ci
    provider-config: |
      {
        "token": "${{ secrets.GITLAB_TOKEN }}",
        "project_id": "boostsecurityio/test-runner-gitlab",
        "ref": "main"
      }
```

| Field | Required | Description |
|-------|----------|-------------|
| `token` | Yes | GitLab Personal Access Token with API permissions |
| `project_id` | Yes | Project ID (numeric) or path (e.g., "org/project") |
| `ref` | No | Branch to run pipeline on (default: "main") |

### Pipeline Variables

The provider passes test configuration as pipeline variables:
- `SCANNER_ID`: Scanner being tested (e.g., "boostsecurityio/trivy-fs")
- `REGISTRY_REF`: Git commit SHA of the registry
- `REGISTRY_REPO`: Registry repository in org/repo format
- `MATRIX_TESTS`: JSON array of test matrix entries

### Project ID Handling

The `project_id` can be either:
- A numeric ID (e.g., `"12345"`)
- A URL-encoded path (e.g., `"boostsecurityio%2Ftest-runner"`)
- An unencoded path (e.g., `"boostsecurityio/test-runner"`) - the provider will URL-encode it automatically

## Azure DevOps Provider

The `AzureDevOpsProvider` dispatches tests to an Azure DevOps pipeline and polls for completion.

### Configuration

```yaml
- uses: boostsecurityio/scanner-registry-testing/test-action@main
  with:
    provider: azure-devops
    provider-config: |
      {
        "token": "${{ secrets.AZURE_PAT }}",
        "organization": "my-org",
        "project": "my-project",
        "pipeline_id": 42
      }
```

| Field | Required | Description |
|-------|----------|-------------|
| `token` | Yes | Azure DevOps Personal Access Token with Build permissions |
| `organization` | Yes | Azure DevOps organization name |
| `project` | Yes | Azure DevOps project name |
| `pipeline_id` | Yes | Pipeline definition ID (numeric) |

### Template Parameters

The provider passes test configuration as pipeline template parameters:
- `SCANNER_ID`: Scanner being tested (e.g., "boostsecurityio/trivy-fs")
- `REGISTRY_REF`: Git commit SHA of the registry
- `REGISTRY_REPO`: Registry repository in org/repo format
- `MATRIX_TESTS`: JSON array of test matrix entries

### Authentication

Azure DevOps uses Basic authentication with an empty username and the Personal Access Token as the password. The token is automatically base64-encoded by the provider.

## Bitbucket Pipelines Provider

The `BitbucketProvider` dispatches tests to a Bitbucket Pipeline and polls for completion.

### Configuration

```yaml
- uses: boostsecurityio/scanner-registry-testing/test-action@main
  with:
    provider: bitbucket
    provider-config: |
      {
        "token": "${{ secrets.BITBUCKET_TOKEN }}",
        "workspace": "my-workspace",
        "repo_slug": "test-runner-bitbucket",
        "branch": "main"
      }
```

| Field | Required | Description |
|-------|----------|-------------|
| `token` | Yes | Bitbucket OAuth access token |
| `workspace` | Yes | Bitbucket workspace slug |
| `repo_slug` | Yes | Repository slug |
| `branch` | No | Branch to run pipeline on (default: "main") |

### Pipeline Variables

The provider passes test configuration as custom pipeline variables:
- `SCANNER_ID`: Scanner being tested (e.g., "boostsecurityio/trivy-fs")
- `REGISTRY_REF`: Git commit SHA of the registry
- `REGISTRY_REPO`: Registry repository in org/repo format
- `MATRIX_TESTS`: JSON array of test matrix entries

### Custom Pipeline Selector

The provider triggers a custom pipeline with the pattern `test-scanner`. Your `bitbucket-pipelines.yml` should define this custom pipeline:

```yaml
pipelines:
  custom:
    test-scanner:
      - step:
          name: Run Scanner Tests
          script:
            - echo "Running tests for $SCANNER_ID"
```

### Authentication

Bitbucket uses OAuth Bearer token authentication. The token should have permissions to trigger pipelines on the target repository.

# Scan Test Action

## Development Rules

### Code Style

- **Immutable return types**: Prefer `Sequence[T]` over `list[T]` for return types
- **Public functions for tested code**: If a function is worth having dedicated tests, make it public (no `_` prefix)
- **No `pragma: no cover`**: Find ways to test error paths instead of skipping coverage

### Testing

- **Integration tests over mocked unit tests**: For code that uses external resources (git, filesystem), write integration tests with real resources
- **Use pytest fixtures**: Create fixtures like `git_repo`, `git_commit` to set up test environments
- **Test order matches source order**: Test classes should appear in the same order as functions in the source file

### Project Structure

- Source code: `scan_test_action/`
- Models: `scan_test_action/models/`
- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Module tests: `tests/module/` (E2E tests using act + WireMock)
- Test fixtures: `tests/integration/conftest.py`, `tests/module/conftest.py`

### Models

- **No code in `__init__.py`**: Keep init files minimal, put implementations in dedicated modules
- **Use `Model` base class**: All models inherit from `scan_test_action.models.base.Model` (frozen by default)
- **Immutable collections**: Use `Sequence[T]` for lists, `Mapping[K, V]` for dicts in model fields
- **Avoid undefined concepts**: Don't add fields for features that aren't yet defined
- **Test file naming**: Test files match source files (e.g., `test_definition.py` for `definition.py`)

### Providers

- **Frozen dataclass base**: `PipelineProvider` is a `@dataclass(frozen=True, kw_only=True)` for immutability
- **Generic state passing**: `PipelineProvider[T]` where `T` is the dispatch state type, avoiding internal mutable state
- **Concrete wait logic**: Base class implements `wait_for_completion()`, providers only implement dispatch/poll
- **Poll returns None when not ready**: `poll_status()` returns `Sequence[TestResult] | None` - results when complete, None when still running (avoids redundant boolean)
- **Module per provider**: Each provider lives in its own module (e.g., `providers/github_actions/`) with config, models, and provider
- **Single session lifecycle**: Use `@classmethod` + `@asynccontextmanager` named `from_config` to manage aiohttp session
- **Pydantic for API responses**: Parse third-party API responses with Pydantic models containing only consumed fields
- **Dispatch ID for matching**: Generate UUID on dispatch, match in workflow display_title for deterministic run finding

### Provider Plugin System

- **Entry points for registration**: Providers are registered in `pyproject.toml` under `[tool.poetry.plugins."scan_test_action.providers"]`
- **Manifest as instance, not class**: Use `provider_manifest = ProviderManifest(...)` not subclasses - simpler when no behavior is added
- **Pass factory directly**: Store `provider_factory=Provider.from_config` directly instead of storing the class and calling `from_config` indirectly - avoids `type: ignore` hacks
- **snake_case for module-level instances**: Use `github_actions_manifest` not `GitHubActionsManifest` for instances
- **Run `make install` after modifying plugins**: Entry points are only updated when the package is reinstalled

### Provider Testing

- **Integration tests with aioresponses**: Mock HTTP calls using `aioresponses` fixture from `tests/integration/conftest.py`
- **Provider fixture**: Create provider via `from_config` async context manager in fixture
- **Configurable base URL**: Include `api_base_url` in config with default, override in tests for mocking

### Module Testing (E2E with act + WireMock)

Module tests run the full GitHub Action using `act` locally with WireMock mocking provider APIs.

- **act for local GitHub Actions**: Use `act push --network {network} -j test` to run workflows locally in Docker
- **WireMock testcontainers**: Use `WireMockContainer` from `wiremock.testing.testcontainer` for API mocking
- **Docker networking**: Containers communicate via Docker network, not localhost - use `http://wiremock:8080` as API base URL
- **Session-scoped fixtures**: WireMock and network fixtures are session-scoped for efficiency across tests
- **Static dispatch_id for WireMock**: Use `dispatch_id_mode: "static"` in GitHub Actions provider config since WireMock cannot share state between POST dispatch and GET poll requests
- **Future timestamps**: Use timestamps in the future (e.g., 2099) for mock workflow runs to pass validation
- **Content-Type header required**: WireMock responses must include `Content-Type: application/json` for aiohttp to parse JSON
- **Local action mapping**: Use `--local-repository test-action/scan-test-action@main={path}` to map workflow action references to local code

### Unit Testing with Mocks

- **Use `Mock(spec=Class)`**: Pass the class as spec parameter to get attribute validation
- **No need to pre-define async methods**: With `spec=`, Mock auto-creates attributes on access
- **Type annotation is `Mock`**: Use `Mock` type in test function parameters, not `MagicMock`
- **Behavioral tests only**: Don't patch internal functions; drive tests through injected dependencies
- **Don't test simple dataclasses**: No need to test that frozen dataclasses are immutable
- **Standalone functions over classes**: When there's only one test suite, use plain test functions instead of a class

### Git Conventions

- **Branch naming**: `{TICKET}-{N}-{description}` for stacked PRs where N is the stack number
- **Commit prefix**: Include Jira ticket ID (e.g., `BST-17998`)

## PR Plan

See `PR_PLAN.md` for the productization roadmap.

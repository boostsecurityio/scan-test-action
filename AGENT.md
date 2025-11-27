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
- Test fixtures: `tests/integration/conftest.py`

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

### Git Conventions

- **Branch naming**: `{TICKET}-{N}-{description}` for stacked PRs where N is the stack number
- **Commit prefix**: Include Jira ticket ID (e.g., `BST-17998`)

## PR Plan

See `PR_PLAN.md` for the productization roadmap.

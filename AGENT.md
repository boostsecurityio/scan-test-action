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
- Integration tests: `tests/integration/`
- Test fixtures: `tests/integration/conftest.py`

### Git Conventions

- **Branch naming**: `{TICKET}-{N}-{description}` for stacked PRs where N is the stack number
- **Commit prefix**: Include Jira ticket ID (e.g., `BST-17998`)

## PR Plan

See `PR_PLAN.md` for the productization roadmap.

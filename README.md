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

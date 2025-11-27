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

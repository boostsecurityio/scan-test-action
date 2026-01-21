"""Test factories for GitHub Actions provider."""

from typing import Any

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from scan_test_action.models.definition import Test, TestDefinition, TestSource


class TestSourceFactory(ModelFactory[TestSource]):
    """Factory for TestSource."""


class TestFactory(ModelFactory[Test]):
    """Factory for Test."""

    scan_paths: Any = Use(list[str])
    env: Any = Use(lambda: {})


class TestDefinitionFactory(ModelFactory[TestDefinition]):
    """Factory for TestDefinition."""

    allowed_env_prefixes: Any = Use(lambda: [])
    tests: Any = Use(list[Test])

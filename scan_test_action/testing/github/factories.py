"""Test factories for GitHub Actions provider."""

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from scan_test_action.models.definition import Test, TestDefinition, TestSource


class TestSourceFactory(ModelFactory[TestSource]):
    """Factory for TestSource."""


class TestFactory(ModelFactory[Test]):
    """Factory for Test."""

    scan_paths = Use(list[str])


class TestDefinitionFactory(ModelFactory[TestDefinition]):
    """Factory for TestDefinition."""

    tests = Use(list[Test])

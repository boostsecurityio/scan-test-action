"""Test factories for generating test data."""

from polyfactory.factories import DataclassFactory

from scan_test_action.models.result import TestResult


class TestResultFactory(DataclassFactory[TestResult]):
    """Factory for TestResult."""

    __model__ = TestResult

    message = None
    run_url = None

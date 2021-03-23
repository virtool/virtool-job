"""Test utilities for Virtool Workflows."""
from typing import Callable, Union

import pytest

from virtool_workflow.environment import WorkflowEnvironment
from virtool_workflow.fixtures.scoping import workflow_fixtures
from virtool_workflow.runtime import fixtures
from virtool_workflow.storage.paths import context_directory


def testing_data_path():
    with context_directory("virtool") as data_path:
        yield data_path


@pytest.fixture
async def runtime(http, jobs_api_url):
    async with WorkflowEnvironment(
            fixtures.runtime
    ) as _runtime:
        _runtime.override("data_path", testing_data_path)
        _runtime["http"] = http
        _runtime["jobs_api_url"] = jobs_api_url
        yield _runtime


def mock_fixture(fixture: Union[str, Callable]):
    if not isinstance(fixture, str):
        fixture = fixture.__name__

    def _add_mock_fixture(func: Callable):
        workflow_fixtures[fixture] = func
        return func

    return _add_mock_fixture


def install_as_pytest_fixtures(_globals, *fixtures):
    """Create pytest fixtures for each fixture in a given :class:`FixtureGroup`."""
    for fixture in fixtures:
        _globals[fixture.__name__] = pytest.fixture(fixture)


__all__ = [
    "runtime",
    "mock_fixture",
    "install_as_pytest_fixtures"
]

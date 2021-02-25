"""Test utilities for Virtool Workflows."""
from typing import Callable, Union

import pytest

from virtool_workflow.analysis.runtime import AnalysisWorkflowEnvironment
from virtool_workflow.data_model import Job
from virtool_workflow.fixtures import FixtureGroup
from virtool_workflow.fixtures.scoping import workflow_fixtures
from virtool_workflow.storage.paths import context_directory


def testing_data_path():
    with context_directory("virtool") as data_path:
        yield data_path


@pytest.fixture
async def runtime():
    async with AnalysisWorkflowEnvironment(
            Job("test_job", {}),
    ) as _runtime:
        _runtime.override("data_path", testing_data_path)
        yield _runtime


def mock_fixture(fixture: Union[str, Callable]):
    if not isinstance(fixture, str):
        fixture = fixture.__name__

    def _add_mock_fixture(func: Callable):
        workflow_fixtures[fixture] = func
        return func

    return _add_mock_fixture


def install_as_pytest_fixtures(fixtures: FixtureGroup):
    """Create pytest fixtures for each fixture in a given :class:`FixtureGroup`."""
    for name, fixture in fixtures.items():
        globals()[name] = pytest.fixture(fixture)


__all__ = [
    "runtime",
    "mock_fixture"
]

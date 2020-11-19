"""Find workflows and fixtures from python modules."""
from importlib import import_module
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from types import ModuleType
from typing import List, Union, Iterable, Tuple, Optional

from virtool_workflow import Workflow, WorkflowFixture
from virtool_workflow.decorator_api import collect

FixtureImportType = Iterable[
    Union[
        str,
        Iterable[str]
    ]
]


def _import_module_from_file(module_name: str, path: Path) -> ModuleType:
    """
    Import a module from a file

    :param module_name: The name of the python module.
    :param path: The :class:`pathlib.Path` of the python file
    :returns: The loaded python module.
    """
    spec = spec_from_file_location(module_name, path)
    module = spec.loader.load_module(module_from_spec(spec).__name__)
    return module


def discover_fixtures(module: Union[Path, ModuleType]) -> List[WorkflowFixture]:
    """
    Find all instances of #execution.fixtures.workflow_fixture.WorkflowFixture in a python module.

    :param module: The path to the python module to import
    :return: A list of all #WorkflowFixture instances contained
        in the module
    """
    if isinstance(module, Path):
        module = _import_module_from_file(module.name.rstrip(module.suffix), module)

    return [attr for attr in module.__dict__.values() if isinstance(attr, WorkflowFixture)]


def load_fixtures_from__fixtures__(path: Path) -> List[WorkflowFixture]:
    """
    Load all fixtures specified by the __fixtures__ attribute of a module.

    :param path: The path to a python module containing __fixtures__: FixtureImportType attribute
    :return: A list of discovered fixtures
    :raise AttributeError: When the imported module does not have an __fixtures__ attribute
    """
    module = _import_module_from_file(path.name.rstrip(path.suffix), path)

    __fixtures__ = getattr(module, "__fixtures__", None)
    if not __fixtures__:
        return []

    fixtures = []
    for fixture_set in __fixtures__:
        if isinstance(fixture_set, str):
            fixtures.extend(discover_fixtures(import_module(fixture_set)))
        else:
            iter_ = iter(fixture_set)
            module = import_module(next(iter_))
            fixtures.extend(getattr(module, name) for name in iter_
                            if isinstance(getattr(module, name), WorkflowFixture))

    return fixtures


def discover_workflow(path: Path) -> Workflow:
    """
    Find a instance of virtool_workflow.Workflow in the python module located at the given path.

    :param path: The #pathlib.Path to the python file containing the module
    :returns: The first instance of #virtool_workflow.Workflow occurring in `dir(module)`

    :raises StopIteration: When no instance of virtool_workflow.Workflow can be found.
    """
    module = _import_module_from_file(path.name.rstrip(path.suffix), path)

    workflow = next((attr for attr in module.__dict__.values() if isinstance(attr, Workflow)), None)

    if not workflow:
        workflow = collect(module)

    return workflow


def run_discovery(
        path: Path,
        fixture_path: Optional[Path] = None
) -> Tuple[Workflow, List[WorkflowFixture]]:
    """
    Discover a workflow and fixtures from the given path(s).

    Fixtures are loaded in the following order:

        1. virtool_workflow_runtime.autoload, used to standard runtime fixtures.
        2. __fixtures__ attribute from the workflow file (located by `path`)
        3. Any #WorkflowFixture instances from the module located by `fixture_path`

    :param path: A Path locating a python module which contains a #Workflow instance
    :param fixture_path: A Path locating a file containing #WorkflowFixture instances
    :return: The Workflow instance from `path` and a list of discovered fixtures.
    """
    fixtures = load_fixtures_from__fixtures__(Path(__file__).parent/"autoload.py")

    fixtures.extend(load_fixtures_from__fixtures__(path))

    if fixture_path and fixture_path.exists():
        fixtures.extend(discover_fixtures(fixture_path))

    workflow = discover_workflow(path)

    return workflow, fixtures

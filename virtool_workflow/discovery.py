"""Find workflows and fixtures from python modules."""
import sys
from importlib import import_module

import logging
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path
from types import ModuleType
from typing import Callable
from typing import List, Union, Iterable, Tuple, Optional

from virtool_workflow.decorator_api import collect
from virtool_workflow.workflow import Workflow

logger = logging.getLogger(__name__)

FixtureImportType = Iterable[Union[str, Iterable[str]]]


class WorkflowDiscoveryError(Exception):
    ...


def import_module_from_file(module_name: str, path: Path) -> ModuleType:
    """
    Import a module from a file.

    The parent directory of `path` will also be added to `sys.path` prior to 
    importing. This ensures that modules and packages defined in that directory 
    can be properly imported.

    :param module_name: The name of the python module.
    :param path: The :class:`pathlib.Path` of the python file
    :returns: The loaded python module.
    """
    module_parent = str(path.parent)
    sys.path.append(module_parent)
    spec = spec_from_file_location(module_name, path)
    module = spec.loader.load_module(module_from_spec(spec).__name__)
    sys.path.remove(module_parent)
    return module


def discover_fixtures(module: Union[Path, ModuleType]) -> List[Callable]:
    """
    Find all instances of #execution.fixtures.workflow_fixture.WorkflowFixture in a python module.

    :param module: The path to the python module to import
    :return: A list of all #WorkflowFixture instances contained
        in the module
    """

    if isinstance(module, Path):
        module = import_module_from_file(
            module.name.rstrip(module.suffix), module)

    return [
        attr for attr in module.__dict__.values()
        if isinstance(attr, Callable)
    ]


def load_fixture_plugins(fixture_modules: Iterable[str]):
    """
    Load fixtures from a set of modules.

    :param fixture_modules: A list of python module names
    :return: A list containing all fixtures present across the given modules.
    """
    fixtures = []
    for fixture_set in fixture_modules:
        if isinstance(fixture_set, str):
            fixtures.extend(discover_fixtures(import_module(fixture_set)))
        else:
            iter_ = iter(fixture_set)
            module = import_module(next(iter_))
            fixtures.extend(
                getattr(module, name) for name in iter_
                if isinstance(getattr(module, name), Callable)
            )

    return fixtures


def load_fixtures_from__fixtures__(path: Path) -> List[Callable]:
    """
    Load all fixtures specified by the __fixtures__ attribute of a module.

    :param path: The path to a python module containing __fixtures__ attribute
    :return: A list of discovered fixtures, or an empty list
             if the `__fixtures__` attribute is absent
    """
    module = import_module_from_file(path.name.rstrip(path.suffix), path)

    __fixtures__ = getattr(module, "__fixtures__", None)
    if not __fixtures__:
        return []

    return load_fixture_plugins(__fixtures__)


def discover_workflow(path: Path) -> Workflow:
    """
    Find a instance of virtool_workflow.Workflow in the
    python module located at the given path.

    :param path: The :class:`pathlib.Path` to the python file
                 containing the module.
    :returns: The first instance of :class:`virtool_workflow.Workflow`
              occurring in `dir(module)`

    :raises StopIteration:
        When no instance of virtool_workflow.Workflow can be found.
    """
    logger.info(f"Importing module from {path}")
    try:
        module = import_module_from_file(path.name.rstrip(path.suffix), path)
    except FileNotFoundError as not_found:
        raise WorkflowDiscoveryError(
            f"There is no such file {path}") from not_found

    workflow = next(

        (attr
         for attr in module.__dict__.values() if isinstance(attr, Workflow)
         ),
        None
    )

    if not workflow:
        return collect(module)

    return workflow


def run_discovery(
        path: Path,
        fixture_path: Optional[Path] = None
) -> Tuple[Workflow, List[Callable]]:
    """
    Discover a workflow and fixtures from the given path(s).

    :param path: A Path to the workflow module
    :param fixture_path: A Path to a module conaining addtional fitures.
    :return: A :class:`Workflow` instance and a list of fixtures.
    """
    logger.info("Beginning workflow discovery.")
    fixtures = load_fixtures_from__fixtures__(
        Path(__file__).parent / "autoload.py")

    logger.info("Loaded fixtures from `autoload.py`")

    fixtures.extend(load_fixtures_from__fixtures__(path))

    logger.info(f"Loaded fixtures from __fixtures__ in {path}")

    if fixture_path and fixture_path.exists():
        fixtures.extend(discover_fixtures(fixture_path))

        logger.info(f"Loaded {fixture_path}")

    workflow = discover_workflow(path)

    logger.info(f"Discovered Workflow {workflow}")

    return workflow, fixtures

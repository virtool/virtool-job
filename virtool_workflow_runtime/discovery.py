from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
from types import ModuleType
from typing import List

from virtool_workflow import Workflow, WorkflowFixture


def _import_module_from_file(module_name: str, path: Path) -> ModuleType:
    """
    Import a module from a file

    :param module_name: The name of the python module.
    :param path: The :class:`pathlib.Path` of the python file
    :returns: The loaded python module.
    """
    spec = spec_from_file_location(module_name, str(path.absolute()))
    module = spec.loader.load_module(module_from_spec(spec).__name__)
    return module


def discover_fixtures(path: Path) -> List[WorkflowFixture]:
    """
    Find all instances of :class:`WorkflowFixture` in a python module.

    :param path: The path to the python module to import
    :return: A list of all :class:`WorkflowFixture` instances contained
        in the module
    """
    module = _import_module_from_file(path.name.rstrip(path.suffix), path)

    return [attr for attr in module.__dict__.values() if isinstance(attr, WorkflowFixture)]


def discover_workflow(path: Path) -> Workflow:
    """
    Find a instance of virtool_workflow.Workflow in the python module located at the given path.

    :param path: The :class:`pathlib.Path` to the python file containing the module
    :returns: The first instance of :class:`virtool_workflow.Workflow` occurring in `dir(module)`

    :raises StopIteration: When no instance of virtool_workflow.Workflow can be found.
    """
    module = _import_module_from_file(path.name.rstrip(path.suffix), path)

    return next((getattr(module, attr) for attr in dir(module) if isinstance(getattr(module, attr), Workflow)))

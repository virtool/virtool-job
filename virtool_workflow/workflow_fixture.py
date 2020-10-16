"""Pytest-style fixtures for use in Virtool Workflows."""
import asyncio
from typing import Callable, Any, Optional, Iterator, Union, List, Type
from inspect import signature, iscoroutinefunction, isgeneratorfunction
from functools import wraps
from abc import abstractmethod, ABC
from itertools import chain
from contextlib import AbstractContextManager

from virtool_workflow.workflow import Workflow


class WorkflowFixtureMultipleYieldError(ValueError):
    """
    Raised when a generator workflow fixture yields more than once.
    """


class WorkflowFixture(ABC):
    """
    Abstract base class for all workflow fixtures. This class is used primarily to keep
    track of all available fixtures via :func:`WorkflowFixture.__subclasses__`.

    The :func:`workflow_fixture` decorator function creates a new subclass of WorkflowFixture with
    the same name as the function passed to :func:`workflow_fixture`. The decorator
    returns an instance of the newly created class, which is callable with the same
    parameters as the function passed to the decorator.
    """
    param_names: List[str]

    def __init_subclass__(cls, param_names: List[str] = None, param_name: str = None, **kwargs):
        """
        Used to set the parameter names by which this fixture will be accessible
        within a workflow function.

        :param param_names: A list of names for this fixture to be injected for
        :param param_name: A name for this fixture to be injected for
        """
        if not param_names:
            if param_name:
                param_names = [param_name]
            else:
                raise ValueError("Must provide `param_names` or `param_name` argument to subclass")

        cls.param_names = param_names

    @staticmethod
    @abstractmethod
    def __fixture__(*args, **kwargs) -> Type["WorkflowFixture"]:
        """A function producing an instance to be used as a workflow fixture."""

    def __call__(self):
        return self.__fixture__()

    @staticmethod
    def types():
        """
        Get all currently available types of workflow fixtures.

        @return: A dict mapping workflow fixture names to
                 their respective :class:`WorkflowFixture` subclasses
        """
        return {name: cls for cls in WorkflowFixture.__subclasses__() for name in cls.param_names}


class WorkflowFixtureScope(AbstractContextManager):
    """
    A scope maintaining instances of workflow fixtures and binding those fixture instances
    to functions based on parameter names. Any calls to :func:`.bind`
    will bind the exact same instances for any given workflow fixture.
    """

    def __init__(self):
        self._instances = {}
        self._generators = []

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self._instances = {}
        # return control to the generator fixtures which are still left open
        for gen in self._generators:
            none = next(gen, None)
            if none is not None:
                raise WorkflowFixtureMultipleYieldError("Fixture must only yield once")
        self._generators = []

    async def instantiate(self, fixture_: Type[WorkflowFixture]) -> Any:
        """
        Create an instance of a workflow fixture and cache it
        within this WorkflowFixtureScope.
        """
        __fixture__ = getattr(fixture_.__class__, "__fixture__", None)
        if not __fixture__:
            __fixture__ = getattr(fixture_, "__fixture__")

        bound = await self.bind(__fixture__)

        if isgeneratorfunction(__fixture__):
            generator = bound()
            self._generators.append(generator)
            instance = next(generator)
        elif iscoroutinefunction(__fixture__):
            instance = await bound()
        else:
            instance = bound()

        for name in fixture_.param_names:
            self._instances[name] = instance

        return instance

    async def get_or_instantiate(self, name: str):
        """
        Get an instance of the workflow fixture with a given name. If there exists an
        instance cached in this WorkflowFixtureScope it will returned, else a new instance
        will be created and cached.

        @param name: The name of the workflow fixture to get
        @return: The workflow fixture instance for this WorkflowFixtureScope
        @raise ValueError: When the given name does not correspond to a defined workflow fixture.
        """
        if name in self._instances:
            return self._instances[name]

        fixture_types = WorkflowFixture.types()
        if name in fixture_types:
            return await self.instantiate(fixture_types[name])

        raise ValueError(f"{name} is not defined as a workflow fixture")

    def __getitem__(self, item: str):
        """Get a fixture instance if one is instantiated within this WorkflowFixtureScope."""
        return self._instances.__getitem__(item)

    def __setitem__(self, key: str, value: Any):
        """Add an instance as a fixture with this WorkflowFixtureScope."""
        return self._instances.__setitem__(key, value)

    def add_instance(self, instance: Any, *names: str):
        """
        Add an instance as a fixture within this WorkflowFixtureScope only. The instance
        will be bound directly and no subclass of WorkflowFixture will be created.

        :param instance: The instance to use as a workflow fixture
        :param names: Any names the workflow fixture should be accessible by
                      (in function parameters)
        """
        for name in names:
            self.__setitem__(name, instance)

    async def bind(self, func: Callable, **kwargs) -> Union[Callable[[], Any], Callable[[], Any]]:
        """
        Bind workflow fixtures to the provided function based on the parameter
        names of the function. Positional arguments and non-fixture keyword arguments
        of the function will be preserved. Essentially,The fixtures & other keyword
        arguments given are added as keyword arguments to the function.

        @param func: The function requiring workflow fixtures to be bound
        @param kwargs: Any other arguments that should be bound to the function
        @return: A new function with it's arguments appropriately bound
        """
        sig = signature(func)
        fixture_types = WorkflowFixture.types()

        fixtures = {param: await self.get_or_instantiate(param)
                    for param in sig.parameters
                    if param in chain(fixture_types, self._instances)}

        fixtures.update(kwargs)

        if iscoroutinefunction(func):
            @wraps(func)
            async def bound(*args, **_kwargs) -> Iterator[Any]:
                _kwargs.update(fixtures)
                return await func(*args, **_kwargs)
        else:
            @wraps(func)
            def bound(*args, **_kwargs) -> Any:
                _kwargs.update(fixtures)
                return func(*args, **_kwargs)

        return bound

    async def bind_to_workflow(self, workflow: Workflow):
        """
        Bind workflow fixtures to all functions for a given Workflow
        :param workflow: The Workflow requiring workflow fixtures

        :return: A new workflow with fixtures bound to all functions
        """
        bound_workflow = Workflow()
        bound_workflow.on_startup = [await self.bind(f) for f in workflow.on_startup]
        bound_workflow.on_cleanup = [await self.bind(f) for f in workflow.on_cleanup]
        bound_workflow.steps = [await self.bind(f) for f in workflow.steps]
        return bound_workflow


def fixture(func: Callable, name: Optional[str] = None):
    """
    Decorator for defining a new :class:`WorkflowFixture`. A subclass of
    :class:`WorkflowFixture` is created with the same name as the provided
    function. An instance of the new subclass which is callable with the same
    parameters as the original function is then returned. This allows the fixture
    to be discovered automatically via :func:`.__subclasses__`.

    Workflow fixtures can be either async or standard functions. They can also be
    generator functions which only yield a single value. Any code after the yield statement
    will be executed when the :class:`WorkflowFixtureScope` closes.

    @param func: A function returning some value to be used as a workflow fixture
    @param name: A name for the created fixture, by default the name of `func` is used
    @return: An instance of a WorkflowFixture subclass that acts like the original function.
    """
    class _Fixture(WorkflowFixture, param_names=[func.__name__]):
        __fixture__ = func

    _Fixture.__name__ = _Fixture.__qualname__ = name if name else func.__name__
    return _Fixture()

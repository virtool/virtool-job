import inspect
from typing import List, Any, Callable, Coroutine, Type
from abc import ABC, abstractmethod

from virtool_workflow.utils import coerce_to_coroutine_function


class IncompatibleCallback(ValueError):
    """Raised when a callback function is not compatible with a Hook"""
    pass


class ParameterMismatch(IncompatibleCallback):
    """Raised when the parameters of a callback function are not compatible with a Hook."""
    pass


class TypeHintMismatch(ParameterMismatch):
    """
    Raised when the type hints of a positional parameter
    do not match between a callback function and a hook definition.
    """
    pass


def _extract_params(func: Callable, extract_return: bool = False):
    """Extract parameters from the signature of a function."""
    signature = inspect.signature(func)
    parameters = signature.parameters
    if extract_return:
        return list(parameters.values()), signature.return_annotation
    return list(parameters.values())


def _validate_parameters(
        hook_name: str,
        callback: Callable,
        hook_params: List[inspect.Parameter],
        callback_params: List[inspect.Parameter]
):
    """Validate that the signatures of the hook function and callback function are compatible. """
    if len(callback_params) != len(hook_params):
        if all(callback_param.kind != inspect.Parameter.VAR_POSITIONAL for callback_param in callback_params):
            raise ParameterMismatch(f"{callback} takes {len(callback_params)} parameters "
                                    f"where {hook_name} takes {len(hook_params)} parameters.")
    for hook_param, callback_param in zip(hook_params, callback_params):
        if hook_param.annotation is inspect.Parameter.empty:
            continue
        if callback_param.annotation is inspect.Parameter.empty:
            continue
        if hook_param.annotation != callback_param.annotation:
            raise TypeHintMismatch(f"({callback_param}) of {callback} does not "
                                   f"match the type of ({hook_param}) of {hook_name}.")


class Hook:
    """A standard hook."""

    def __init__(self, hook_name, parameters, return_type):
        self.name = hook_name
        self._params = parameters
        self._return = return_type
        # TODO: verify return type
        self.callbacks = []

    def __call__(self, callback_: Callable) -> Callable:
        return self.callback(callback_)

    def callback(self, callback_: Callable) -> Callable:
        callback_params = _extract_params(callback_)
        _validate_parameters(self.name, callback_, self._params, callback_params)
        self.callbacks.append(coerce_to_coroutine_function(callback_))
        return callback_

    async def trigger(self, *args, **kwargs) -> List[Any]:
        return [await callback(*args, **kwargs) for callback in self.callbacks]


def hook(func: Callable):
    """Create a hook based on a function signature."""
    parameters, return_annotation = _extract_params(func, extract_return=True)
    return Hook(str(func), parameters, return_annotation)


def create_hook(name: str, *param_types, return_type=None):
    return Hook(name,
                [inspect.Parameter("", inspect.Parameter.POSITIONAL_ONLY, annotation=typ)
                 for typ in param_types],
                return_type=return_type)


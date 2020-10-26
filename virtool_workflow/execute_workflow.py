"""Execute workflows without runtime related hooks (database, redis, etc.)."""
import sys
import traceback
from typing import Awaitable, Callable, Optional, Dict, Any

from .context import WorkflowExecutionContext, UpdateListener, State
from .workflow import Workflow, WorkflowStep
from .fixtures.scope import WorkflowFixtureScope


class WorkflowError(Exception):
    """

    An exception occurring during the execution of a workflow.
    """

    def __init__(
            self,
            cause: Exception,
            workflow: Workflow,
            context: WorkflowExecutionContext,
            max_traceback_depth: int = 50
    ):
        """

        :param cause: The initial exception raised
        :param workflow: The workflow object being executed
        :param context: The execution context of the workflow being executed
        :param max_traceback_depth: The maximum depth for the traceback data
        """
        self.cause = cause
        self.workflow = workflow
        self.context = context

        exception, value, trace_info = sys.exc_info()

        self.traceback_data = {
            "type": exception.__name__,
            "traceback": traceback.format_tb(trace_info, max_traceback_depth),
            "details": [str(arg) for arg in value.args]
        }

        super().__init__(str(cause))


WorkflowErrorHandler = Callable[[WorkflowError], Awaitable[Optional[str]]]
"""Handler function for when a :class:`WorkflowError` is raised during execution of a Workflow"""


async def _run_step(
        step: WorkflowStep,
        workflow: Workflow,
        ctx: WorkflowExecutionContext,
        on_error: Optional[WorkflowErrorHandler] = None
):
    ctx.error = None
    try:
        return await step()
    except Exception as exception:
        error = WorkflowError(cause=exception, workflow=workflow, context=ctx)
        ctx.error = error.traceback_data
        if on_error:
            return await on_error(error)

        raise error from exception


async def _run_steps(steps, workflow, ctx, on_error=None, on_each=None):
    for step in steps:
        if on_each:
            on_each(workflow, ctx)
        update = await _run_step(step, workflow, ctx, on_error)
        await ctx.send_update(update)


def _inc_step(workflow, ctx):
    ctx.current_step += 1
    ctx.progress = float(ctx.current_step) / float(len(workflow.steps))


async def execute(
        _wf: Workflow,
        _context: WorkflowExecutionContext = None,
        scope: WorkflowFixtureScope = None,
        on_update: Optional[UpdateListener] = None,
        on_state_change: Optional[UpdateListener] = None,
        on_error: Optional[WorkflowErrorHandler] = None
) -> Dict[str, Any]:
    """
    Execute a Workflow.

    :param Workflow _wf: the Workflow to execute
    :param _context: The WorkflowExecutionContext to start from
    :param scope: The WorkflowFixtureScope to use for fixture injection
    :param on_update: An async function which is called when a step of
        the workflow provides an update
    :param on_state_change: An async function which is called when the WorkflowState changes
    :param on_error: An async function which is called upon any exception
    :raises WorkflowError: If any Exception occurs during execution it is caught and wrapped in
        a WorkflowError. The initial Exception is available by the `cause` attribute.
    """
    _context = _context if _context else WorkflowExecutionContext()

    if on_update:
        _context.on_update(on_update)
    if on_state_change:
        _context.on_state_change(on_state_change)

    scope = scope if scope else WorkflowFixtureScope()
    with scope as execution_scope:

        execution_scope.add_instance(_wf, "wf", "workflow")
        execution_scope.add_instance(_context, "context", "execution_context", "ctx")
        execution_scope.add_instance({}, "result", "results")

        bound = await execution_scope.bind_to_workflow(_wf)

        await _context.set_state(State.STARTUP)
        await _run_steps(bound.on_startup, bound, _context, on_error=on_error)
        await _context.set_state(State.RUNNING)
        await _run_steps(bound.steps, bound, _context, on_each=_inc_step, on_error=on_error)
        await _context.set_state(State.CLEANUP)
        await _run_steps(bound.on_cleanup, bound, _context, on_error=on_error)
        await _context.set_state(State.FINISHED)

        return scope["result"]

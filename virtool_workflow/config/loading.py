import logging
from virtool_workflow import hooks
from virtool_workflow.execution.hooks.fixture_hooks import FixtureHook
from virtool_workflow.fixtures.scope import FixtureScope

from .fixtures import options

logger = logging.getLogger(__name__)


async def load_config(scope: FixtureScope = None, hook: FixtureHook = None, **kwargs):
    """
    Override config fixture values with those from :obj:`kwargs`.

    Triggers `on_load_config` hook.

    :param kwargs: Values for any config options to be used before the fixtures.
    """
    if not hook:
        hook = hooks.on_load_config

    for option in options.values():
        if option.name in kwargs:
            if kwargs[option.name] is not None:
                logger.info(
                    f"Overriding '{option.name}'"
                    f"with value '{kwargs[option.name]}'")
                option.override_value = (
                    option.transform(
                        kwargs[option.name]
                    ) or kwargs[option.name]
                )

            del kwargs[option.name]

    if kwargs:
        raise ValueError(f"{list(kwargs)} are not configuration options")

    if not scope:
        async with FixtureScope(options) as config_scope:
            await hook.trigger(config_scope)
    else:
        scope.add_provider(options)
        await hook.trigger(scope)

from abc import abstractmethod, ABC
from typing import Dict, Any

from virtool_workflow.discovery import load_fixture_plugins
from virtool_workflow.workflow import Workflow


class AbstractWorkflowEnvironment(ABC):

    @staticmethod
    def load_plugins(*plugin_modules: str):
        """Load fixtures from plugins."""
        return load_fixture_plugins(plugin_modules)

    @abstractmethod
    async def execute(self, workflow: Workflow) -> Dict[str, Any]:
        """Execute a Workflow."""
        ...

    @abstractmethod
    async def execute_function(self, func: callable):
        """Execute a function in the runtime context."""
        ...

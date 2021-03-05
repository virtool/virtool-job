from abc import ABC, abstractmethod
from numbers import Number
from pathlib import Path
from typing import Dict

from virtool_workflow.data_model import Subtraction


class AbstractSubtractionProvider(ABC):

    @abstractmethod
    async def get(self) -> Subtraction:
        """Get the subtraction."""
        ...

    @abstractmethod
    async def finalize(self, gc: Dict[str, Number]):
        """Store the gc and finalize the subtraction."""
        ...

    @abstractmethod
    async def delete(self):
        """Permanently delete the subtraction."""
        ...

    @abstractmethod
    async def upload(self, path: Path):
        """Upload files relating to the subtraction."""

    @abstractmethod
    async def download(self, target_path: Path, *names):
        """Download files relating to the subtraction."""

    def __await__(self):
        return self.get().__await__()

from abc import ABC, abstractmethod
from importlib.metadata import version as package_version
from typing import ClassVar

from ...support.naming import Naming
from ...support.runtime import drive
from ..capability import Capability
from ..engine import Engine

Hit = dict[str, str | float]


class SearchEngine(Engine, ABC):
    """The I/O bound side of the registry, async sources under the sync Engine surface.

    A search source's real implementation is the async `fetch`. The `recall`
    verb awaits `search`, the guarded entry, on every source inside one event
    loop, while the inherited sync `Engine.run` path keeps working through
    `execute`, which drives `fetch` on a fresh loop. Compute engines never
    see any of this and the `Engine` contract stays synchronous. Abstract, so
    it never enrolls in the registry itself.
    """

    capability: ClassVar[Capability] = Capability.SEARCH

    def execute(self, payload: str) -> str:
        """Sync facade over `fetch`, keeping the registry contract uniform."""
        return drive(self.fetch(payload))

    @abstractmethod
    async def fetch(self, payload: str) -> str:
        """Run one search asynchronously, returning the hits as a JSON array string."""

    async def search(self, payload: str) -> str:
        """Guarded async entry, refusing hosts where this source is unavailable."""
        self.ensure_available()
        return await self.fetch(payload)

    def version(self) -> str:
        """This tool's own version, since it shapes the hits."""
        return package_version(Naming.NAME)

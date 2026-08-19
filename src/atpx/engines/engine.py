from abc import ABC, abstractmethod
from importlib.metadata import PackageNotFoundError, version
from typing import ClassVar

from patos import Registry

from .capability import Capability
from .exceptions import EngineUnavailableError
from .importable import is_importable


class Engine(Registry, ABC):
    """Registry root for engines, each stamping name and version into evidence.

    A concrete engine declares its import `module`, its installed `distribution`
    name, and the one `capability` it serves. The layer stays deliberately
    minimal because atpx certifies results and never proxies APIs; agents
    import sympy or flint directly in their own snippets.
    """

    name: ClassVar[str]
    module: ClassVar[str]
    distribution: ClassVar[str]
    capability: ClassVar[Capability]
    precedence: ClassVar[int] = 0

    @classmethod
    def supporting(cls, capability: Capability | str) -> list[type[Engine]]:
        """Concrete engines serving a capability, most preferred first.

        Preference is the declared `precedence`, lowest first, with the
        registration order breaking ties, so the roster no longer depends on
        which module happened to import first.
        """
        wanted = Capability(capability)
        serving = [engine for engine in cls.implementations() if engine.capability is wanted]
        return sorted(serving, key=lambda engine: engine.precedence)

    def available(self) -> bool:
        """Whether this engine can run on this host."""
        return is_importable(self.module)

    def ensure_available(self) -> None:
        """Refuse this engine on a host where it cannot run."""
        if not self.available():
            raise EngineUnavailableError(f"{self.name} is not available on this host")

    @abstractmethod
    def execute(self, payload: str) -> str:
        """Run this engine's capability on a payload, returning the raw result string."""

    def run(self, operation: Capability | str, payload: str) -> str:
        """Guarded sync entry: validate the capability and refuse unavailable hosts.

        operation: the requested capability.
        payload: the operation input.
        """
        Capability(operation)
        self.ensure_available()
        return self.execute(payload)

    def version(self) -> str:
        """The installed engine version, `unknown` when the distribution is absent."""
        try:
            return version(self.distribution)
        except PackageNotFoundError:
            return "unknown"

from abc import ABC, abstractmethod
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from typing import ClassVar

from patos import Registry


class Capability(StrEnum):
    """The typed operations engines implement; v2 keeps only read-only search."""

    SEARCH = "search"


class EngineUnavailableError(RuntimeError):
    """Raised when an operation is requested from an engine this host cannot run."""


class UnsupportedOperationError(LookupError):
    """Raised when an engine is asked for an operation outside its capability."""


def importable(module: str) -> bool:
    """Whether `module` can be imported here, without importing it.

    module: the import name to probe.
    """
    try:
        return find_spec(module) is not None
    except ModuleNotFoundError:
        return False


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

    def available(self) -> bool:
        """Whether this engine can run on this host."""
        return importable(self.module)

    def version(self) -> str:
        """The installed engine version, `unknown` when the distribution is absent."""
        try:
            return version(self.distribution)
        except PackageNotFoundError:
            return "unknown"

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

    @classmethod
    def supporting(cls, capability: Capability | str) -> list[type[Engine]]:
        """Concrete engines serving a capability, in registration (preference) order."""
        wanted = Capability(capability)
        return [engine for engine in cls.implementations() if engine.capability is wanted]

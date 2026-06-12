import decimal
from abc import ABC, abstractmethod
from enum import StrEnum
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from typing import ClassVar

from patos import Registry

DIGITS = 30
COMPARED_DIGITS = 20


class Capability(StrEnum):
    """The typed operations engines implement, atpx's cross-engine vocabulary."""

    EVALUATE = "evaluate"
    FACTOR = "factor"
    SOLVE_SMT = "solve-smt"
    PROVE_TPTP = "prove-tptp"
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


def normalized(capability: Capability, value: str) -> str:
    """Canonical form of an engine result so independent engines compare equal.

    Numeric evaluations are rounded to a shared significand so formatting noise
    in the last digits never masks or fakes agreement; everything else is
    compared verbatim after trimming whitespace.

    capability: the operation that produced the value.
    value: one engine's raw result string.
    """
    if capability is Capability.EVALUATE:
        context = decimal.Context(prec=COMPARED_DIGITS)
        return str(context.create_decimal(value).normalize(context))
    return value.strip()


class Engine(Registry, ABC):
    """Registry root for computation engines, each stamping name and version into evidence.

    A concrete engine declares its import `module`, its installed `distribution`
    name, and the one `capability` it serves; stage 2 grows the vocabulary by
    adding engines and capabilities, never by editing this contract.

    The layer stays deliberately minimal (availability, version, run and stamp,
    cross-engine agreement) and grows no per-function typed wrappers, because atpx
    certifies results and never proxies APIs, agents import sympy or flint or z3
    directly in their own snippets. Zettel "Prova Proof Bookkeeping Package", the
    no-proxy principle section.
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
        """Guarded entry point: refuse unsupported operations and unavailable hosts.

        operation: the requested capability.
        payload: the operation input, an expression, integer, or goal text.
        """
        requested = Capability(operation)
        if requested is not self.capability:
            raise UnsupportedOperationError(
                f"{self.name} only does {self.capability.value}, not {requested.value}"
            )
        self.ensure_available()
        return self.execute(payload)

    @classmethod
    def supporting(cls, capability: Capability | str) -> list[type[Engine]]:
        """Concrete engines serving a capability, in registration (preference) order."""
        wanted = Capability(capability)
        return [engine for engine in cls.implementations() if engine.capability is wanted]

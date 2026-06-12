import sys
from importlib import import_module
from typing import ClassVar

import flint
import mpmath
import sympy

from .base import DIGITS, Capability, Engine, importable


class SympyEngine(Engine):
    """Exact symbolic evaluation through sympy."""

    name = "sympy"
    module: ClassVar[str] = "sympy"
    distribution: ClassVar[str] = "sympy"
    capability: ClassVar[Capability] = Capability.EVALUATE

    def execute(self, payload: str) -> str:
        """Parse `payload` symbolically and evaluate it to a high-precision decimal."""
        return str(sympy.N(sympy.sympify(payload), DIGITS))


class MpmathEngine(Engine):
    """Arbitrary-precision numeric evaluation through mpmath."""

    name = "mpmath"
    module: ClassVar[str] = "mpmath"
    distribution: ClassVar[str] = "mpmath"
    capability: ClassVar[Capability] = Capability.EVALUATE

    def execute(self, payload: str) -> str:
        """Evaluate `payload` in the mpmath namespace at working precision."""
        with mpmath.workdps(DIGITS):
            value = eval(payload, {"__builtins__": {}}, dict(vars(mpmath)))
            return str(mpmath.nstr(mpmath.mpmathify(value), DIGITS))


class FlintEngine(Engine):
    """Exact integer arithmetic through python-flint."""

    name = "flint"
    module: ClassVar[str] = "flint"
    distribution: ClassVar[str] = "python-flint"
    capability: ClassVar[Capability] = Capability.FACTOR

    def execute(self, payload: str) -> str:
        """Factor the integer `payload` into the canonical `p^e` product string."""
        factors = flint.fmpz(int(payload)).factor()
        return " ".join(f"{prime}^{power}" for prime, power in sorted(factors))


class PariEngine(Engine):
    """Quadratic forms and number theory through cypari2's bundled PARI.

    The cypari2 wheel only installs cleanly on linux-64 (see the chefe.toml
    overlay), so this engine reports unavailable everywhere else and the import
    happens lazily at execution time.
    """

    name = "pari"
    module: ClassVar[str] = "cypari2"
    distribution: ClassVar[str] = "cypari2"
    capability: ClassVar[Capability] = Capability.FACTOR
    platform: ClassVar[str] = sys.platform

    def available(self) -> bool:
        """Linux-only, and only when the optional cypari2 wheel is installed."""
        return self.platform == "linux" and importable(self.module)

    def execute(self, payload: str) -> str:
        """Factor the integer `payload` through PARI into the same `p^e` form."""
        pari = import_module(self.module).Pari()
        decomposition = pari.factor(int(payload))
        pairs = zip(decomposition[0], decomposition[1], strict=True)
        return " ".join(f"{prime}^{power}" for prime, power in sorted(pairs))

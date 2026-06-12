import re
import shutil
import tempfile
from pathlib import Path
from typing import ClassVar

from plumbum import local

from .base import Capability, Engine

SZS_STATUS = re.compile(r"SZS status (\w+)")


class TptpProverMixin:
    """Shared subprocess plumbing for first-order provers speaking TPTP and SZS.

    Not an Engine itself, so only the concrete provers enroll in the registry.
    The prover binary must be on PATH for the engine to report available.
    """

    binary: ClassVar[str]
    arguments: ClassVar[tuple[str, ...]] = ()

    def available(self) -> bool:
        """Whether the prover binary is on PATH."""
        return shutil.which(self.binary) is not None

    def version(self) -> str:
        """First line of `<binary> --version`."""
        return local[self.resolved()]("--version").strip().splitlines()[0]

    def execute(self, payload: str) -> str:
        """Prove the TPTP `payload`, returning the SZS status word.

        Theorem means the conjecture was closed; anything else, including a
        missing SZS line reported as Unknown, leaves the goal open.
        """
        with tempfile.TemporaryDirectory() as scratch:
            problem = Path(scratch) / "goal.p"
            problem.write_text(payload)
            _, stdout, stderr = local[self.resolved()][*self.arguments, str(problem)].run(
                retcode=None
            )
        match = SZS_STATUS.search(stdout + stderr)
        return match.group(1) if match else "Unknown"

    def resolved(self) -> str:
        """The binary's current PATH location, dodging plumbum's lookup cache."""
        return shutil.which(self.binary) or self.binary


class EProverEngine(TptpProverMixin, Engine):
    """The E theorem prover as a subprocess engine."""

    name = "eprover"
    binary: ClassVar[str] = "eprover"
    arguments: ClassVar[tuple[str, ...]] = ("--auto", "--silent")
    capability: ClassVar[Capability] = Capability.PROVE_TPTP


class VampireEngine(TptpProverMixin, Engine):
    """The Vampire theorem prover as a subprocess engine."""

    name = "vampire"
    binary: ClassVar[str] = "vampire"
    capability: ClassVar[Capability] = Capability.PROVE_TPTP

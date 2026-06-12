from typing import ClassVar

import cvc5
import z3

from .base import Capability, Engine


class Z3Engine(Engine):
    """SMT solving through Z3.

    The payload is SMT-LIB 2 text holding declarations and assertions; atpx
    issues the final satisfiability check itself, so goals omit `(check-sat)`.
    """

    name = "z3"
    module: ClassVar[str] = "z3"
    distribution: ClassVar[str] = "z3-solver"
    capability: ClassVar[Capability] = Capability.SOLVE_SMT

    def execute(self, payload: str) -> str:
        """Load the SMT-LIB assertions and report sat, unsat, or unknown."""
        solver = z3.Solver()
        solver.from_string(payload)
        return str(solver.check())


class Cvc5Engine(Engine):
    """SMT solving through cvc5, an implementation independent from Z3.

    Takes the same `(check-sat)`-free SMT-LIB 2 payload convention as Z3Engine.
    """

    name = "cvc5"
    module: ClassVar[str] = "cvc5"
    distribution: ClassVar[str] = "cvc5"
    capability: ClassVar[Capability] = Capability.SOLVE_SMT

    def execute(self, payload: str) -> str:
        """Parse the SMT-LIB commands, invoke them, and report sat, unsat, or unknown."""
        # cvc5 re-exports everything from a compiled extension with no stubs, a genuine
        # third-party stub gap pyrefly cannot see into.
        solver = cvc5.Solver()  # pyrefly: ignore[missing-attribute]
        parser = cvc5.InputParser(solver)  # pyrefly: ignore[missing-attribute]
        language = cvc5.InputLanguage.SMT_LIB_2_6  # pyrefly: ignore[missing-attribute]
        parser.setStringInput(language, payload, self.name)
        manager = parser.getSymbolManager()
        while not (command := parser.nextCommand()).isNull():
            command.invoke(solver, manager)
        return str(solver.checkSat())

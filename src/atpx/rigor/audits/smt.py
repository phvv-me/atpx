from .audit import witnesses


class SmtAudit:
    """The smt gate: at least one printed smt certificate, every one unsat.

    A `sat` result is a counterexample, evidence worth keeping in the output,
    but never a validation, so it fails the gate while the model stays visible.
    """

    rigor = "smt"
    key = "smt_certificate"

    def violation(self, output: str) -> str:
        """Why the output does not earn smt rigor, empty when it does."""
        lines = witnesses(output, key=self.key)
        if not lines:
            return "no smt_certificate line printed"
        settled = [
            f"{line.get('name')}={line.get('result')}"
            for line in lines
            if line.get("result") != "unsat"
        ]
        if settled:
            return (
                f"smt results are not unsat ({', '.join(settled)}); "
                "a sat model is a counterexample, not a validation"
            )
        return ""

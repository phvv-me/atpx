from patos import FrozenModel


class Petition(FrozenModel):
    """One settle request: the journal message and the artifact references offered."""

    message: str = ""
    judgment: str | None = None
    counterexample: str | None = None
    certificate: str | None = None
    lean: str | None = None

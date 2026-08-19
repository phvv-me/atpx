from patos import FrozenModel


class Attempt(FrozenModel):
    """One prover episode's outcome over at most `repairs` repair rounds."""

    slug: str
    claim: str
    passed: bool
    rounds: int
    probe: str
    violation: str = ""

from patos import FrozenModel


class Submission(FrozenModel):
    """One detached claim run, recorded beside its log in the blueprint's `checks/` dir."""

    claim: str
    submitted: str
    pid: int

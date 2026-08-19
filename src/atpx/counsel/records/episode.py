from patos import FrozenModel


class Episode(FrozenModel):
    """One attack lane's mechanical outcome, the emitted verdict already discarded."""

    claim: str
    model: str
    demonstrated: bool
    detail: str
    stdout: str = ""

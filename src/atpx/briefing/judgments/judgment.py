from patos import FrozenModel


class Judgment(FrozenModel):
    """A full node snapshot taken the moment a refuter logs a ruling.

    A verbatim snapshot, not a hash and not git, is the simplest reliable diff
    base. It needs no repository around the node file and always yields a real
    text diff, where a hash could only say that something changed.
    """

    text: str
    timestamp: str

from enum import StrEnum, auto


class Kind(StrEnum):
    """What a blueprint node claims to be, stamped once at scaffold time."""

    LEMMA = auto()
    THEOREM = auto()
    DEFINITION = auto()
    COUNTEREXAMPLE = auto()
    EXPERIMENT = auto()

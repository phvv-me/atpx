from enum import StrEnum, auto


class Status(StrEnum):
    """Lifecycle of a proof node, the one mutable field on a node file.

    `validated` sits between `sketched` and `verified`: the central claim
    carries a rigorous machine certificate (ball, smt, or exact) without a
    kernel-checked proof yet. `known` marks a literature collision, the claim
    is true but already in the record, distinct from `refuted` and never a
    novelty.
    """

    OPEN = auto()
    IN_PROGRESS = auto()
    SKETCHED = auto()
    VALIDATED = auto()
    REFUTED = auto()
    VERIFIED = auto()
    ABANDONED = auto()
    KNOWN = auto()

    @property
    def is_settled(self) -> bool:
        """Whether a node in this status is done: judged, decided, or shelved."""
        return self in {
            Status.SKETCHED,
            Status.VALIDATED,
            Status.REFUTED,
            Status.VERIFIED,
            Status.ABANDONED,
            Status.KNOWN,
        }

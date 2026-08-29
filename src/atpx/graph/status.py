from enum import StrEnum, auto


class Status(StrEnum):
    """Lifecycle of a proof node, the one mutable field on a node file.

    `validated` sits between `sketched` and `verified`: the central claim
    carries a rigorous machine certificate (ball, smt, or exact) without a
    kernel-checked proof yet.

    Three words end a node without carrying it up that ladder, and they say
    three different things. `undecided` is a verdict and not a failure: the
    experiment ran clean and the comparison the node registered cannot separate
    the outcomes, which is the honest reading of a question whose answer is
    inside the noise. `abandoned` drops a line of attack, so the question stands
    and nobody is working it. `known` marks a literature collision, the claim is
    true but already in the record, distinct from `refuted` and never a novelty.
    """

    OPEN = auto()
    IN_PROGRESS = auto()
    SKETCHED = auto()
    VALIDATED = auto()
    REFUTED = auto()
    VERIFIED = auto()
    UNDECIDED = auto()
    ABANDONED = auto()
    KNOWN = auto()

    @property
    def is_settled(self) -> bool:
        """Whether a node in this status is done: judged, decided, or shelved.

        Named one by one rather than as everything past `in_progress`, so a status
        added later has to say for itself that it ends a node.
        """
        return self in {
            Status.SKETCHED,
            Status.VALIDATED,
            Status.REFUTED,
            Status.VERIFIED,
            Status.UNDECIDED,
            Status.ABANDONED,
            Status.KNOWN,
        }

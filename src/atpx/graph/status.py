from enum import StrEnum, auto


class Status(StrEnum):
    """Lifecycle of a proof node, the one mutable field on a node file.

    The ladder opens with three words for a node that has not run yet, and the
    distinction between them is the registration regime rather than bookkeeping.
    `open` is a question somebody wrote down. `proposed` is an idea with a shape,
    named and argued for but with nothing frozen. `registered` is a specification
    committed BEFORE the runs it governs, so its decision rule, its scope and its
    seal are in the record and cannot be chosen after the numbers arrive; that is
    what makes a later result confirmatory rather than exploratory. None of the
    three settles anything, so a registered node still sits on the frontier and
    still owes its run.

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
    PROPOSED = auto()
    REGISTERED = auto()
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
        added later has to say for itself that it ends a node. `proposed` and
        `registered` say the opposite: a registration is a promise about a run that
        has not happened, and reading it as settled would count an owed campaign as
        a finding.
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

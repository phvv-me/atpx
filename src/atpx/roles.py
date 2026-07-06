from enum import StrEnum


class Status(StrEnum):
    """Lifecycle of a proof node, the one mutable field on a zettel.

    `known` marks a literature collision, the claim is true but already in the
    record, distinct from `refuted` and never a novelty.
    """

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    SKETCHED = "sketched"
    REFUTED = "refuted"
    VERIFIED = "verified"
    ABANDONED = "abandoned"
    KNOWN = "known"


SETTLED = frozenset(
    {Status.SKETCHED, Status.REFUTED, Status.VERIFIED, Status.ABANDONED, Status.KNOWN}
)

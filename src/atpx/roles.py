from enum import StrEnum


class Role(StrEnum):
    """Who is acting on a node, per the math-loop certification ladder."""

    MATHEMATICIAN = "mathematician"
    PROVER = "prover"
    REFUTER = "refuter"
    FORMALIZER = "formalizer"


class Status(StrEnum):
    """Lifecycle of a proof node, the one mutable field on a zettel."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    SKETCHED = "sketched"
    REFUTED = "refuted"
    VERIFIED = "verified"
    ABANDONED = "abandoned"


SETTLED = frozenset({Status.SKETCHED, Status.REFUTED, Status.VERIFIED, Status.ABANDONED})

GRANTS: dict[Role, frozenset[Status]] = {
    Role.MATHEMATICIAN: frozenset({Status.OPEN, Status.IN_PROGRESS, Status.ABANDONED}),
    Role.PROVER: frozenset({Status.IN_PROGRESS}),
    Role.REFUTER: frozenset({Status.SKETCHED, Status.REFUTED}),
    Role.FORMALIZER: frozenset({Status.VERIFIED}),
}


class RoleError(PermissionError):
    """Raised when a role tries a status transition the ladder forbids."""


def authorize(role: Role, status: Status) -> None:
    """Refuse in code, not prose, any transition the certification ladder forbids.

    role: who is asking.
    status: the status they want to set.
    """
    if status not in GRANTS[role]:
        allowed = ", ".join(sorted(s.value for s in GRANTS[role]))
        raise RoleError(f"{role.value} may not set {status.value}, only {allowed}")

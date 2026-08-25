from enum import StrEnum, auto


class Category(StrEnum):
    """What a node is for, derived from its `kind`: most kinds state a claim.

    `probe-pool` directories carry shared probe libraries and no claim, so the
    completeness lints exempt them; a `convention` binds reporting rather than
    truth but still states itself and its refutation condition like any claim.
    """

    CLAIM = auto()
    CONVENTION = auto()
    PROBE_POOL = auto()

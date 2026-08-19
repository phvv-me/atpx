from patos import FrozenModel

from .episode import Episode


class Referral(FrozenModel):
    """The refuter fan-out's mechanical outcome over one node, for the mathematician."""

    slug: str
    verdict: str
    episodes: list[Episode]
    draft: str

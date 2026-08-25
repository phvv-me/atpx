from patos import FrozenModel

from .episode import Episode


class Referral(FrozenModel):
    """The refuter fan-out's mechanical outcome over one node, for the mathematician.

    `rung` is the strongest ladder position that attacked, the number a survival
    judgment is worth: a sketch citing this referral is as strong as the lane
    that fought that bout, named in `boss`.
    """

    slug: str
    verdict: str
    rung: int
    boss: str
    episodes: list[Episode]
    draft: str

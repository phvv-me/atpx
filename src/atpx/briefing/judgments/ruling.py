from patos import FrozenModel

from .severity import Severity


class Ruling(FrozenModel):
    """One judgment on one claim: who ruled, when, how hard, and where the reasoning is.

    The machine-checkable half of counsel. The reasoning stays prose, in the review file
    `prose` names, because that is what a referee actually produces and what a
    mathematician actually reads; what lands in the record is the standing a lint can
    check. A human referee and a model lane write the same shape, which is what lets an
    external review count as evidence in the graph rather than as a file only a person
    opens.

    referee: the model lane id or the human name that ruled.
    date: the ISO date the ruling was made.
    ruling: how badly it cut, FATAL, GAP, MINOR, or NONE.
    claim: what was attacked, the node's own name or a numbered claim inside it.
    prose: the review file this line summarizes, node-directory-relative.
    rung: the ladder position that attacked, empty for a referee outside the ladder.
    """

    referee: str
    date: str
    ruling: Severity
    claim: str
    prose: str = ""
    rung: str = ""

from pydantic import JsonValue

from ....counsel.bout import Context
from ....counsel.refuter import Refuter
from ...foundation import Slug
from ...state import FoundationState


class RefuteVerbs(FoundationState):
    """Summon the refuter fan-out over one node and compute the mechanical verdict."""

    def refute(
        self,
        slug: Slug,
        n: int = 4,
        *,
        rounds: int = 3,
        tries: int = 1,
        context: Context = "live",
    ) -> dict[str, JsonValue]:
        """Climb the refuter ladder over one node and compute the mechanical verdict.

        Each roster lane is a rung fought as a bout: the boss swings attack
        probes, the prover lane answers every demonstrated attack with a
        defense probe, and every move is machine-gated, no side ever argues
        in prose. The climb stops at the first bout the defense loses, a
        FATAL candidate, else the node survived every rung. The draft
        judgment lands under the blueprint's `judgments/` for semantic
        review, and settling stays with the mathematician.

        slug: the blueprint directory name holding the node.
        n: the maximum number of bouts.
        rounds: each boss's attack budget per bout.
        tries: per-move gate-repair budget for each side.
        context: `live` keeps each boss's history, `fresh` restarts per round.
        """
        roster = self.lanes.ladder
        referral = Refuter(roster, defender=self.lanes.prover).fanout(
            self, slug, n, rounds=rounds, tries=tries, context=context
        )
        return referral.model_dump(mode="json", exclude={"episodes": {"__all__": {"stdout"}}})

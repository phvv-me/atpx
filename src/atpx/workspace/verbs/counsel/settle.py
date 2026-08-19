from ....graph.status import Status
from ....settlement.moving import Settlement
from ....settlement.petition import Petition
from ...foundation import ClaimRef, Slug, StatusName
from ...state import FoundationState


class SettleVerbs(FoundationState):
    """Move a node's status, gated on evidence artifacts rather than claimed roles."""

    def settle(
        self,
        slug: Slug,
        status: StatusName,
        message: str = "",
        *,
        judgment: str | None = None,
        counterexample: ClaimRef = None,
        certificate: str | None = None,
        lean: ClaimRef = None,
    ) -> str:
        """Move a node's status, gated on evidence artifacts rather than claimed roles.

        `sketched` demands a judgment file, `refuted` a counterexample
        certificate in the node's ledgers, `validated` a persisted certificate
        whose rigor is ball, smt, or exact with exit 0, `verified` a clean
        Lean certificate with zero sorries and no flagged risky axioms. The
        free statuses (open, in_progress, abandoned, known) need none.

        slug: the blueprint directory name holding the node.
        status: the target lifecycle status.
        message: the one-line journal entry body.
        judgment: path to the recorded refuter ruling, required for sketched.
        counterexample: claim id of a persisted counterexample certificate, for refuted.
        certificate: claim id of a persisted rigorous certificate, for validated.
        lean: claim id of a persisted clean Lean certificate, for verified.
        """
        target, node = Status(status), self.nodes.find(slug)
        petition = Petition(
            message=message,
            judgment=judgment,
            counterexample=counterexample,
            certificate=certificate,
            lean=lean,
        )
        return Settlement(self.root).move(node, target, petition)

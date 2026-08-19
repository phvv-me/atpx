from pathlib import Path
from typing import ClassVar

from ..graph.node import Node
from ..graph.status import Status
from .exceptions import SettleError
from .gate import Gate
from .petition import Petition

_RIGOROUS = {"ball", "smt", "exact"}


class ValidateGate(Gate):
    """`validated` demands a clean certificate whose rigor is ball, smt, or exact."""

    status: ClassVar[Status] = Status.VALIDATED

    def granted(self, node: Node, root: Path, petition: Petition) -> str:
        """Demand the rigorous certificate, refusing sampled rigor and dirty exits."""
        witness = self.demand(node, petition.certificate)
        if witness.rigor not in _RIGOROUS:
            raise SettleError(
                f"{witness.claim} carries rigor {witness.rigor!r}, "
                f"validated needs one of {sorted(_RIGOROUS)}"
            )
        if not witness.ok:
            raise SettleError(f"{witness.claim} exited {witness.exit_status}, cannot validate")
        return f"certificate {witness.claim}"

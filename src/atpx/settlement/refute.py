from pathlib import Path
from typing import ClassVar

from ..graph.node import Node
from ..graph.status import Status
from .gate import Gate
from .petition import Petition


class RefuteGate(Gate):
    """`refuted` demands a persisted counterexample certificate in the node's ledgers."""

    status: ClassVar[Status] = Status.REFUTED

    def granted(self, node: Node, root: Path, petition: Petition) -> str:
        """Demand the counterexample certificate and name it in the journal."""
        witness = self.demand(node, petition.counterexample)
        return f"counterexample {witness.claim}"

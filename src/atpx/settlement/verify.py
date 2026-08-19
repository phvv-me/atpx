from pathlib import Path
from typing import ClassVar

from ..graph.node import Node
from ..graph.status import Status
from .exceptions import SettleError
from .gate import Gate
from .petition import Petition


class VerifyGate(Gate):
    """`verified` demands a clean Lean build certificate, zero sorries and nothing flagged."""

    status: ClassVar[Status] = Status.VERIFIED

    def granted(self, node: Node, root: Path, petition: Petition) -> str:
        """Demand the Lean certificate, refuse dirty builds and risky axioms."""
        certificate = self.demand(node, petition.lean)
        audit = certificate.result if isinstance(certificate.result, dict) else {}
        if not certificate.ok or audit.get("sorries", 1):
            raise SettleError(f"{certificate.claim} is not a clean Lean build, cannot verify")
        if audit.get("flagged"):
            raise SettleError(
                f"{certificate.claim} leans on risky axioms {audit['flagged']}, cannot verify"
            )
        return f"lean {certificate.claim}"

from pathlib import Path
from typing import ClassVar

from ..briefing.judgments.ledger import JudgmentLedger
from ..graph.node import Node
from ..graph.status import Status
from .exceptions import SettleError
from .gate import Gate
from .petition import Petition


class SketchGate(Gate):
    """`sketched` demands the recorded refuter ruling and snapshots the judged node."""

    status: ClassVar[Status] = Status.SKETCHED

    def commit(self, node: Node, root: Path) -> None:
        """Snapshot the node as judged right now, the diff base `judge_brief` reads."""
        JudgmentLedger(node.directory).record(node)

    def granted(self, node: Node, root: Path, petition: Petition) -> str:
        """Demand a ruling file that exists root-relative or as given."""
        ruling = Path(petition.judgment) if petition.judgment else None
        found = ruling is not None and ((root / ruling).exists() or ruling.exists())
        if not found:
            raise SettleError("sketched requires --judgment pointing at the recorded ruling")
        return f"judgment {petition.judgment}"

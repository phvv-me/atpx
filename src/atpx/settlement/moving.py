from pathlib import Path

from ..graph.journal import LogEntry
from ..graph.node import Node
from ..graph.status import Status
from .gate import Gate
from .petition import Petition


class Settlement:
    """Moves node statuses behind the evidence gates, journaling every move."""

    def __init__(self, root: Path) -> None:
        """root: the workspace root the blueprint ledgers resolve against."""
        self.root = root

    def move(self, node: Node, target: Status, petition: Petition) -> str:
        """Demand the gate's artifact, journal the move, set the status, commit.

        node: the node whose status moves.
        target: the destination lifecycle status.
        petition: the message and artifact references offered.
        """
        gate = Gate.of(target)
        reference = gate.granted(node, self.root, petition) if gate else ""
        body = " ".join(part for part in (petition.message, reference) if part)
        entry = LogEntry.today(who="settle", tag=target.value, message=body)
        node.append_log(str(entry))
        node.set_status(target)
        if gate:
            gate.commit(node, self.root)
        return str(entry)

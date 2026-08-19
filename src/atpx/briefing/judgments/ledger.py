from datetime import UTC, datetime
from pathlib import Path

from ...graph.node import Node
from .judgment import Judgment


class JudgmentLedger:
    """The latest judgment snapshot per node, `judgments/<node>.json` in a blueprint dir."""

    def __init__(self, directory: Path) -> None:
        """directory: the blueprint directory the node's evidence lives in."""
        self.directory = directory / "judgments"

    def latest(self, node: str) -> Judgment | None:
        """The recorded judgment for a node, None before any ruling."""
        try:
            return Judgment.model_validate_json(self.path(node).read_text())
        except FileNotFoundError:
            return None

    def path(self, node: str) -> Path:
        """Where one node's snapshot lives."""
        return self.directory / f"{node}.json"

    def record(self, node: Node) -> Path:
        """Snapshot the node as judged right now, replacing any earlier snapshot."""
        judgment = Judgment(text=node.text, timestamp=datetime.now(UTC).isoformat())
        path = self.path(node.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(judgment.model_dump_json(indent=2) + "\n")
        return path

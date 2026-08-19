from pathlib import Path

from .node import Node
from .status import Status


class NodeStore:
    """The blueprints root seen as a graph of proof nodes, one `node.md` per blueprint.

    Membership is existence: every blueprint directory holding a `node.md` is a
    node, no tag gating, so an untagged node can never silently vanish from a
    fleet view. A malformed or absent status lands in the `invalid` bucket
    `doctor` reports instead.
    """

    def __init__(self, path: Path) -> None:
        """path: the blueprints root directory."""
        self.path = path

    def find(self, slug: str) -> Node:
        """The node of blueprint `slug`, raising with the known slugs on a miss.

        slug: the blueprint directory name a wikilink would use.
        """
        node = Node(self.path / slug / Node.FILENAME)
        if not node.path.exists():
            raise KeyError(
                f"no node named {slug!r}; known nodes are "
                f"{', '.join(other.name for other in self.nodes())}"
            )
        return node

    def frontier(self) -> list[dict[str, str | dict[str, str] | dict[str, list[str]]]]:
        """Open or in-progress nodes whose in-store dependencies are all settled.

        The leanblueprint frontier idea over wikilinks: these are the nodes ready
        to be worked next.
        """
        nodes = {node.name: node for node in self.nodes()}
        ready = []
        for node in nodes.values():
            if node.status is not None and node.status.is_settled:
                continue
            others = [link for link in node.links if link in nodes and link != node.name]
            dependencies = {link: nodes[link].status for link in others}
            if all(status is not None and status.is_settled for status in dependencies.values()):
                entry: dict[str, str | dict[str, str] | dict[str, list[str]]] = {
                    "node": node.name,
                    "status": str(node.status),
                    "deps": {name: str(status) for name, status in dependencies.items()},
                }
                if node.relations:
                    entry["relations"] = node.relations
                ready.append(entry)
        return ready

    def nodes(self) -> list[Node]:
        """Every blueprint node, sorted by slug."""
        return [Node(p) for p in sorted(self.path.glob(f"*/{Node.FILENAME}"))]

    def statuses(self) -> dict[str, list[str]]:
        """Node names grouped by status, ordered down the certification ladder.

        Nodes carrying a status string outside the ladder, or none at all,
        land in an `invalid` bucket with the offending value, never an
        exception.
        """
        nodes = self.nodes()
        groups = {
            status.value: names
            for status in Status
            if (names := sorted(node.name for node in nodes if node.status is status))
        }
        invalid = sorted(
            f"{node.name} ({node.raw_status or 'missing'})"
            for node in nodes
            if node.status is None
        )
        if invalid:
            groups["invalid"] = invalid
        return groups

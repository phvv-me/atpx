from collections.abc import Mapping
from pathlib import Path

from .node import Node
from .status import Status

type Row = dict[str, str | dict[str, str] | dict[str, list[str]]]


class NodeStore:
    """The blueprint roots seen as one graph of proof nodes, one `node.md` per blueprint.

    A workspace declares one root or several, and the store reads their union as a
    single graph, so a program whose claims of record moved from a proof tree into an
    experiment tree is still one graph rather than two. Roots are searched in
    declaration order, so a slug that two roots both hold resolves to the first, and
    the first root is where a fresh blueprint lands.

    Membership is existence: every blueprint directory holding a `node.md` is a node,
    no tag gating, so an untagged node can never silently vanish from a fleet view. A
    malformed or absent status lands in the `invalid` bucket `doctor` reports instead.

    A node carrying `superseded_by` is an ALIAS rather than a second claim: it names
    where its node of record moved and it is folded out of `canonical`, which is what
    every count, status view, frontier and index reads, so a claim that moved is
    counted exactly once and always at its current home.
    """

    def __init__(self, *roots: Path) -> None:
        """roots: the blueprint root directories, in declaration order."""
        self.roots = roots

    @property
    def path(self) -> Path:
        """The first declared root, where a blueprint with no home of its own is created."""
        return self.roots[0]

    def aliases(self) -> dict[str, str]:
        """Superseded slugs mapped to the pointer naming their node of record."""
        return {node.name: node.superseded_by for node in self.nodes() if node.superseded}

    def canonical(self) -> list[Node]:
        """Every node that is still its own record, superseded stubs folded out."""
        return [node for node in self.nodes() if not node.superseded]

    def directory(self, slug: str) -> Path:
        """The blueprint directory a slug names: the first root holding it, else the first root.

        A slug no root holds resolves under the first declared root, which is where a
        fresh blueprint lands, so capture-first creation never has to ask which root
        to use.

        slug: the blueprint directory name.
        """
        return self.resolve(slug) or self.path / slug

    def find(self, slug: str) -> Node:
        """The node of blueprint `slug`, raising with the known slugs on a miss.

        slug: the blueprint directory name a wikilink would use.
        """
        found = next(
            (node for node in self.nodes() if node.name == slug),
            None,
        )
        if found is None:
            raise KeyError(
                f"no node named {slug!r}; known nodes are "
                f"{', '.join(other.name for other in self.nodes())}"
            )
        return found

    def frontier(self) -> list[Row]:
        """Open or in-progress nodes whose in-store dependencies are all settled.

        The leanblueprint frontier idea over wikilinks: these are the nodes ready
        to be worked next. A dependency naming a slug that has since been superseded
        resolves through the alias, so the frontier reads the status of the node of
        record rather than of the pointer left behind.
        """
        reachable = self.resolved()
        ready = []
        for node in self.canonical():
            if node.status is not None and node.status.is_settled:
                continue
            dependencies = self.__dependencies(node, reachable)
            if any(status is None or not status.is_settled for status in dependencies.values()):
                continue
            ready.append(self.__row(node, dependencies))
        return ready

    def holds(self, pointer: str) -> bool:
        """Whether some root holds the blueprint a slug or `<root>/<slug>` pointer names.

        pointer: a bare slug, or one qualified by the name of the root holding it.
        """
        return self.resolve(pointer) is not None

    def nodes(self) -> list[Node]:
        """Every blueprint node across the roots, sorted by slug, the first root winning."""
        found: dict[str, Node] = {}
        for root in self.roots:
            for path in sorted(root.glob(f"*/{Node.FILENAME}")):
                found.setdefault(path.parent.name, Node(path))
        return [found[name] for name in sorted(found)]

    def resolve(self, pointer: str) -> Path | None:
        """The blueprint directory a pointer names, None when no root holds it.

        pointer: a bare slug, or one qualified by the name of the root holding it.
        """
        named, _, slug = pointer.rpartition("/")
        for root in self.roots:
            if (not named or root.name == named) and (root / slug).is_dir():
                return root / slug
        return None

    def resolved(self) -> dict[str, Node]:
        """Every node keyed by each slug that reaches it, an alias keyed to its canonical.

        A superseded slug resolves to the node of record its pointer names, so a
        wikilink written before a migration still lands on the claim it meant, and a
        canonical node always wins its own name.
        """
        canonical = {node.name: node for node in self.canonical()}
        aliases = {
            slug: canonical[target]
            for slug, pointer in self.aliases().items()
            if (target := pointer.rpartition("/")[2]) in canonical
        }
        return aliases | canonical

    def statuses(self) -> dict[str, list[str]]:
        """Node names grouped by status, ordered down the certification ladder.

        Superseded stubs are not counted, since their claim is counted at the node
        of record. Nodes carrying a status string outside the ladder, or none at all,
        land in an `invalid` bucket with the offending value, never an exception.
        """
        nodes = self.canonical()
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

    @staticmethod
    def __dependencies(node: Node, nodes: Mapping[str, Node]) -> dict[str, Status | None]:
        """Statuses of the in-store nodes one node links to, itself never counted."""
        return {
            link: nodes[link].status for link in node.links if link in nodes and link != node.name
        }

    @staticmethod
    def __row(node: Node, dependencies: Mapping[str, Status | None]) -> Row:
        """One frontier row, carrying typed relations only when the node states some."""
        row: Row = {
            "node": node.name,
            "status": str(node.status),
            "deps": {name: str(status) for name, status in dependencies.items()},
        }
        if node.relations:
            row["relations"] = node.relations
        return row

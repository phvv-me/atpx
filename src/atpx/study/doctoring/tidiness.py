from pathlib import Path

from pydantic import JsonValue

from ...core.evidence import EvidenceStore
from ...graph.category import Category
from ...graph.node import Node
from ...graph.store import NodeStore
from ...support.naming import Naming
from ..index import LedgerIndex


class TidinessLints:
    """The workspace shape lints: index currency, stray files, and unfinished blueprints."""

    def __init__(self, nodes: NodeStore, *, root: Path, index: LedgerIndex) -> None:
        """nodes: the blueprint node graph the index is generated from.

        root: the workspace root paths report relative to.
        index: the workspace's generated index artifacts, checked for currency.
        """
        self.nodes = nodes
        self.root = root
        self.index = index

    @property
    def blueprints(self) -> list[Path]:
        """Every blueprint directory across the declared roots, sorted by slug."""
        found = {
            directory.name: directory
            for root in self.nodes.roots
            if root.is_dir()
            for directory in root.iterdir()
            if directory.is_dir()
        }
        return [found[name] for name in sorted(found)]

    def compiled(self) -> dict[str, JsonValue]:
        """This group's report slice, one key per lint."""
        return {
            "stale_index": self.stale_index(),
            "undesigned_evidence": self.undesigned(),
            "stray_evidence": self.stray_evidence(),
            "unmanifested_blueprints": self.unmanifested(),
            "nodeless_blueprints": self.nodeless(),
            "superseded_nodes": self.superseded(),
        }

    def nodeless(self) -> list[JsonValue]:
        """Blueprints holding a manifest or evidence but no `node.md`."""
        return list[JsonValue](
            [
                directory.name
                for directory in self.blueprints
                if not (directory / Node.FILENAME).exists()
                and ((directory / Naming.CONFIG).exists() or (directory / "evidence").is_dir())
            ]
        )

    def stale_index(self) -> list[JsonValue]:
        """The index artifacts a regeneration would change, `atpx index` refreshes them."""
        expected = self.nodes.canonical()
        return [path.relative_to(self.root).as_posix() for path in self.index.stale(expected)]

    def stray_evidence(self) -> dict[str, JsonValue]:
        """Files under `evidence/` that are not certificate ledgers, per blueprint."""
        return {
            directory.name: [path.relative_to(self.root).as_posix() for path in stray]
            for directory in self.blueprints
            if (stray := EvidenceStore.strays(directory))
        }

    def superseded(self) -> dict[str, JsonValue]:
        """Stub nodes and the node of record each one now points at.

        Reported rather than gated: a supersession is a migration recorded properly,
        and naming the aliases is what shows a reader why a slug they remember is
        counted at another slug's name.
        """
        return dict[str, JsonValue](self.nodes.aliases())

    def undesigned(self) -> list[JsonValue]:
        """Nodes holding certificates with no pre-registration design file beside them.

        Untidiness rather than a breakage: the discipline wants `design` before the
        run, but evidence captured before the contract existed stays evidence.
        """
        return [
            node.name
            for node in self.nodes.canonical()
            if node.front.category is not Category.PROBE_POOL
            and any(EvidenceStore.ledgers(node.directory).values())
            and not any(node.directory.glob("design-*.md"))
        ]

    def unmanifested(self) -> list[JsonValue]:
        """Blueprint directories without a claim manifest."""
        return list[JsonValue](
            [
                directory.name
                for directory in self.blueprints
                if not (directory / Naming.CONFIG).exists()
            ]
        )

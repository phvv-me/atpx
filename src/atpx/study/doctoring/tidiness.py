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

    def __init__(
        self, nodes: NodeStore, *, blueprints: Path, root: Path, index: LedgerIndex
    ) -> None:
        """nodes: the blueprint node graph the index is generated from.

        blueprints: the blueprints root directory.
        root: the workspace root paths report relative to.
        index: the workspace's generated index artifacts, checked for currency.
        """
        self.nodes = nodes
        self.blueprints = blueprints
        self.root = root
        self.index = index

    def compiled(self) -> dict[str, JsonValue]:
        """This group's report slice, one key per lint."""
        return {
            "stale_index": self.stale_index(),
            "undesigned_evidence": self.undesigned(),
            "stray_evidence": self.stray_evidence(),
            "unmanifested_blueprints": self.unmanifested(),
            "nodeless_blueprints": self.nodeless(),
        }

    def nodeless(self) -> list[JsonValue]:
        """Blueprints holding a manifest or evidence but no `node.md`."""
        return list[JsonValue](
            sorted(
                directory.name
                for directory in self.blueprints.iterdir()
                if directory.is_dir()
                and not (directory / Node.FILENAME).exists()
                and ((directory / Naming.CONFIG).exists() or (directory / "evidence").is_dir())
            )
        )

    def stale_index(self) -> list[JsonValue]:
        """The index artifacts a regeneration would change, `atpx index` refreshes them."""
        return [str(path.relative_to(self.root)) for path in self.index.stale(self.nodes.nodes())]

    def stray_evidence(self) -> dict[str, JsonValue]:
        """Files under `evidence/` that are not certificate ledgers, per blueprint."""
        return {
            directory.name: [str(path.relative_to(self.root)) for path in stray]
            for directory in sorted(self.blueprints.iterdir())
            if directory.is_dir() and (stray := EvidenceStore.strays(directory))
        }

    def undesigned(self) -> list[JsonValue]:
        """Nodes holding certificates with no pre-registration design file beside them.

        Untidiness rather than a breakage: the discipline wants `design` before the
        run, but evidence captured before the contract existed stays evidence.
        """
        return [
            node.name
            for node in self.nodes.nodes()
            if node.front.category is not Category.PROBE_POOL
            and any(EvidenceStore.ledgers(node.directory).values())
            and not any(node.directory.glob("design-*.md"))
        ]

    def unmanifested(self) -> list[JsonValue]:
        """Blueprint directories without a claim manifest."""
        return list[JsonValue](
            sorted(
                directory.name
                for directory in self.blueprints.iterdir()
                if directory.is_dir() and not (directory / Naming.CONFIG).exists()
            )
        )

from pathlib import Path

from pydantic import JsonValue

from ...graph.category import Category
from ...graph.store import NodeStore
from ..results import ResultsLedger


class ReportingLints:
    """The results-table lints: what the program settled against what its results table says.

    The index answers what nodes exist and this answers what the program can be quoted
    as holding. A settled node with no row is a finding nobody outside the node file can
    read, and a row citing a stub sends a reader to the half of a migrated pair that
    stopped receiving evidence. Both are silent by nature, since the table is
    hand-authored and no regeneration ever compares it to the ledger.

    A workspace with no results table beside its index reports nothing here, so the
    lint arrives for the programs that keep one and stays out of the way of the rest.
    """

    def __init__(self, nodes: NodeStore, *, root: Path, results: ResultsLedger) -> None:
        """nodes: the blueprint node graph whose settled claims the table owes rows for.

        root: the workspace root paths report relative to.
        results: the workspace's hand-authored results table.
        """
        self.nodes = nodes
        self.root = root
        self.results = results

    def compiled(self) -> dict[str, JsonValue]:
        """This group's report slice, one key per lint."""
        return {
            "unreported_results": self.unreported(),
            "misdirected_citations": self.misdirected(),
        }

    def misdirected(self) -> dict[str, JsonValue]:
        """Rows citing a superseded stub instead of the node of record its pointer names.

        The citation still resolves, which is what makes it worth reporting: a reader
        following it lands on a pointer whose evidence stopped moving, while the run
        that backs the number is under the name the stub defers to.
        """
        aliases = self.nodes.aliases()
        return {
            slug: f"cite [[{aliases[slug].rpartition('/')[2]}]], "
            f"the node of record {aliases[slug]} this stub points at"
            for slug in sorted(self.results.cited & set(aliases))
        }

    def unreported(self) -> list[JsonValue]:
        """Settled claim nodes the results table carries no row for.

        The table's own rule is that a node that settles earns a row in the tier its
        state earns, and the rule is kept by hand, so a whole campaign can settle
        without one line of it reaching the file a reader is pointed at.
        """
        if not self.results.path.is_file():
            return []
        cited = self.results.cited
        return [
            node.name
            for node in self.nodes.canonical()
            if node.front.category is not Category.PROBE_POOL
            and node.status is not None
            and node.status.is_settled
            and node.name not in cited
        ]

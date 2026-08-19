from ..blueprint.manifest import Blueprint
from ..core.evidence import EvidenceStore
from ..graph.journal import LogEntry
from ..graph.node import Node
from ..graph.store import NodeStore

_FENCE = "````"
_JUDGES = {"refuter", "settle"}


def last_judgment(node: Node) -> LogEntry | None:
    """The node's most recent judgment line, a refuter entry or a settle entry."""
    rulings = [entry for entry in node.log if entry.who in _JUDGES]
    return rulings[-1] if rulings else None


class Briefing:
    """Assembles `brief <slug>`, the one-command agent context bundle, as markdown.

    One structured bundle replaces the opening calls every agent used to spend
    re-reading the same state: the node text, its dependency statuses from the
    wikilink walk, the per-host evidence summary with staleness against the
    current git revision, the last judgment verbatim, and the blueprint files.
    """

    def __init__(self, blueprint: Blueprint, node: Node, nodes: NodeStore, revision: str) -> None:
        """blueprint: the node's claim manifest.

        node: the blueprint-local node carrying the statement, status, and journal.
        nodes: the surrounding graph the dependency walk resolves against.
        revision: the workspace's current git revision, the staleness reference.
        """
        self.blueprint = blueprint
        self.node = node
        self.nodes = nodes
        self.revision = revision

    def dependencies(self) -> str:
        """One line per blueprint dependency with its status, from the wikilink walk."""
        nodes = {node.name: node for node in self.nodes.nodes()}
        links = [name for name in self.node.links if name in nodes and name != self.node.name]
        lines = [f"- [[{name}]] is {nodes[name].status}" for name in links]
        return "\n".join(lines) or "No blueprint dependencies."

    def evidence(self) -> str:
        """One line per host ledger, certificate count, latest revision, stale flag."""
        lines = []
        for host, certificates in EvidenceStore.ledgers(self.blueprint.directory).items():
            newest = max(certificates, key=lambda entry: entry.timestamp)
            staleness = "current" if newest.git_rev == self.revision else "stale"
            lines.append(
                f"- {host} holds {len(certificates)} certificates, "
                f"latest at git_rev {newest.git_rev} ({staleness})"
            )
        return "\n".join(lines) or "No evidence recorded yet."

    def files(self) -> str:
        """The blueprint directory's files, one bullet each."""
        names = sorted(p.name for p in self.blueprint.directory.iterdir() if p.is_file())
        return "\n".join(f"- {name}" for name in names)

    def render(self) -> str:
        """The full markdown bundle."""
        sections = [
            f"# Brief for {self.node.name}",
            f"Status {self.node.status}, workspace revision {self.revision}.",
            "## Node",
            f"{_FENCE}markdown\n{self.node.text.rstrip()}\n{_FENCE}",
            "## Dependencies",
            self.dependencies(),
            "## Evidence",
            self.evidence(),
            "## Last judgment",
            str(last_judgment(self.node) or "No judgment logged yet."),
            "## Blueprint files",
            self.files(),
        ]
        return "\n\n".join(sections) + "\n"

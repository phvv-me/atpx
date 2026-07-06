import difflib
from datetime import UTC, datetime
from pathlib import Path

from .base import FrozenModel
from .blueprint import Blueprint
from .evidence import EvidenceStore
from .zettel import LogEntry, Vault, Zettel

FENCE = "````"
JUDGES = frozenset({"refuter", "settle"})


class Judgment(FrozenModel):
    """A full node snapshot taken the moment a refuter logs a ruling.

    A verbatim snapshot, not a hash and not git, is the simplest reliable diff
    base. It needs no repository around the vault and always yields a real text
    diff, where a hash could only say that something changed.
    """

    text: str
    timestamp: str


class JudgmentLedger:
    """The latest judgment snapshot per node, `judgments/<node>.json` in a blueprint dir."""

    def __init__(self, directory: Path) -> None:
        """directory: the blueprint directory the node's evidence lives in."""
        self.directory = directory / "judgments"

    def path(self, node: str) -> Path:
        """Where one node's snapshot lives."""
        return self.directory / f"{node}.json"

    def record(self, node: Zettel) -> Path:
        """Snapshot the node as judged right now, replacing any earlier snapshot."""
        judgment = Judgment(text=node.text, timestamp=datetime.now(UTC).isoformat())
        path = self.path(node.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(judgment.model_dump_json(indent=2) + "\n")
        return path

    def latest(self, node: str) -> Judgment | None:
        """The recorded judgment for a node, None before any ruling."""
        try:
            return Judgment.model_validate_json(self.path(node).read_text())
        except FileNotFoundError:
            return None


def last_judgment(node: Zettel) -> LogEntry | None:
    """The node's most recent judgment line, a refuter entry or a settle entry."""
    rulings = [entry for entry in node.log if entry.who in JUDGES]
    return rulings[-1] if rulings else None


class Briefing:
    """Assembles `brief <slug>`, the one-command agent context bundle, as markdown.

    One structured bundle replaces the opening calls every agent used to spend
    re-reading the same state: the node text, its dependency statuses from the
    wikilink walk, the per-host evidence summary with staleness against the
    current git revision, the last judgment verbatim, and the blueprint files.
    """

    def __init__(self, blueprint: Blueprint, node: Zettel, vault: Vault, revision: str) -> None:
        """blueprint: the node's claim manifest.

        node: the vault zettel carrying the node's status and journal.
        vault: the surrounding graph the dependency walk resolves against.
        revision: the workspace's current git revision, the staleness reference.
        """
        self.blueprint = blueprint
        self.node = node
        self.vault = vault
        self.revision = revision

    def render(self) -> str:
        """The full markdown bundle."""
        sections = [
            f"# Brief for {self.node.name} ({self.blueprint.slug})",
            f"Status {self.node.status}, workspace revision {self.revision}.",
            "## Node",
            f"{FENCE}markdown\n{self.node.text.rstrip()}\n{FENCE}",
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

    def dependencies(self) -> str:
        """One line per in-vault dependency with its status, from the wikilink walk."""
        nodes = {node.name: node for node in self.vault.nodes()}
        links = [name for name in self.node.links if name in nodes and name != self.node.name]
        lines = [f"- [[{name}]] is {nodes[name].status}" for name in links]
        return "\n".join(lines) or "No in-vault dependencies."

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


class JudgeBriefing:
    """Assembles `judge_brief <slug>`, the delta since the node's last judgment.

    Keeps MINOR re-judgment rounds cheap: a unified diff of the node text against
    the snapshot the last ruling recorded, plus the claims whose certificates
    landed after that ruling's timestamp.
    """

    def __init__(self, blueprint: Blueprint, node: Zettel) -> None:
        """blueprint: the node's claim manifest.

        node: the vault zettel being re-judged.
        """
        self.blueprint = blueprint
        self.node = node
        self.judgment = JudgmentLedger(blueprint.directory).latest(node.name)

    def render(self) -> str:
        """The full markdown delta."""
        header = f"# Judge brief for {self.node.name} ({self.blueprint.slug})"
        if self.judgment is None:
            return (
                f"{header}\n\nNo judgment recorded yet, "
                "the whole node and all its evidence are new to the refuter.\n"
            )
        sections = [
            header,
            f"Last judged {self.judgment.timestamp}.",
            "## Node diff since last judgment",
            self.diff(self.judgment),
            "## Claims with newer certificates",
            self.landed(self.judgment),
        ]
        return "\n\n".join(sections) + "\n"

    def diff(self, judgment: Judgment) -> str:
        """Unified diff of the node text against the judged snapshot."""
        lines = difflib.unified_diff(
            judgment.text.splitlines(),
            self.node.text.splitlines(),
            "judged",
            "current",
            lineterm="",
        )
        body = "\n".join(lines)
        return f"{FENCE}diff\n{body}\n{FENCE}" if body else "Unchanged."

    def landed(self, judgment: Judgment) -> str:
        """Certificate counts per claim stamped after the judgment, one bullet each.

        Claims outside the `slug/` convention (`fit data.csv`) count under
        their full id rather than collapsing into an empty name.
        """
        counts: dict[str, int] = {}
        for certificates in EvidenceStore.ledgers(self.blueprint.directory).values():
            for entry in certificates:
                if entry.timestamp > judgment.timestamp:
                    name = entry.claim.removeprefix(f"{self.blueprint.slug}/")
                    counts[name] = counts.get(name, 0) + 1
        lines = [
            f"- {claim} gained {count} certificates" for claim, count in sorted(counts.items())
        ]
        return "\n".join(lines) or "None."

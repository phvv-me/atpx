import difflib

from ..blueprint.manifest import Blueprint
from ..core.evidence import EvidenceStore
from ..graph.node import Node
from .judgments.judgment import Judgment
from .judgments.ledger import JudgmentLedger

_FENCE = "````"


class JudgeBriefing:
    """Assembles `judge_brief <slug>`, the delta since the node's last judgment.

    Keeps MINOR re-judgment rounds cheap: a unified diff of the node text against
    the snapshot the last ruling recorded, plus the claims whose certificates
    landed after that ruling's timestamp.
    """

    def __init__(self, blueprint: Blueprint, node: Node) -> None:
        """blueprint: the node's claim manifest.

        node: the blueprint-local node being re-judged.
        """
        self.blueprint = blueprint
        self.node = node
        self.judgment = JudgmentLedger(blueprint.directory).latest(node.name)

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
        return f"{_FENCE}diff\n{body}\n{_FENCE}" if body else "Unchanged."

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

    def render(self) -> str:
        """The full markdown delta."""
        header = f"# Judge brief for {self.node.name}"
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

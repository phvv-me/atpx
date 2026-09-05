import re
from pathlib import Path

from pydantic import JsonValue

from ...briefing.judgments.ledger import JudgmentLedger
from ...briefing.judgments.rulings import RulingLedger
from ...graph.category import Category
from ...graph.node import Node, statement_of
from ...graph.status import Status
from ...graph.store import NodeStore

_RUNG = re.compile(r"(?i)\brung\b|refute-\d+-\d+")


class CompletenessLints:
    """The node contract lints: statement, refutation condition, frontmatter, judgments.

    The discipline the research protocol states, verdicted mechanically: a claim
    without a refutation condition is not ready to run, a sketch is worth what
    the strongest rung that attacked it is worth, and a statement that drifted
    from its judgment snapshot is certified by nothing.
    """

    def __init__(self, nodes: NodeStore, *, root: Path) -> None:
        """nodes: the blueprint node graph whose contract is linted.

        root: the workspace root judgment pointers may be relative to.
        """
        self.nodes = nodes
        self.root = root

    def compiled(self) -> dict[str, JsonValue]:
        """This group's report slice, one key per lint."""
        return {
            "invalid_statuses": self.invalid_statuses(),
            "dangling_links": self.dangling(),
            "frontmatter_problems": self.frontmatter_problems(),
            "unstated_nodes": self.unstated(),
            "unconditioned_nodes": self.unconditioned(),
            "unjudged_sketches": self.unjudged_sketches(),
            "drifted_statements": self.drifted(),
        }

    def dangling(self) -> dict[str, JsonValue]:
        """Wikilinks, typed relations, and depends pointing at slugs with no blueprint.

        Read over every node including the superseded stubs, since a stub whose
        `superseded_by` points at nothing is exactly the dangling pointer this lint
        exists to catch.
        """
        report: dict[str, JsonValue] = {}
        for node in self.nodes.nodes():
            targets = dict.fromkeys(
                [
                    *node.links,
                    *(slug for slugs in node.relations.values() for slug in slugs),
                    *node.front.depends,
                ]
            )
            missing = [slug for slug in targets if not self.nodes.holds(slug)]
            if missing:
                report[node.name] = list[JsonValue](missing)
        return report

    def drifted(self) -> dict[str, JsonValue]:
        """Nodes whose statement no longer matches their judgment snapshot verbatim.

        The check the backfill ran by hand, now standing: the snapshot records the
        node as judged, so a statement that differs from it is certified by nothing
        until the node is re-judged.
        """
        report: dict[str, JsonValue] = {}
        for node in self.nodes.canonical():
            snapshot = JudgmentLedger(node.directory).latest(node.name)
            if snapshot is not None and statement_of(snapshot.text) != node.statement:
                report[node.name] = "statement differs from its judgment snapshot"
        return report

    def frontmatter_problems(self) -> dict[str, JsonValue]:
        """Nodes whose frontmatter is missing or fails the contract's tolerant parse."""
        return {
            node.name: list[JsonValue](node.front.problems)
            for node in self.nodes.nodes()
            if node.front.problems
        }

    def invalid_statuses(self) -> dict[str, JsonValue]:
        """Nodes carrying a status outside the lifecycle ladder, or none at all.

        A probe pool is the one shape allowed to carry no status, since it never
        was a claim; a garbage status string is flagged on any node.
        """
        return {
            node.name: node.raw_status
            for node in self.nodes.nodes()
            if node.status is None
            and (node.raw_status or node.front.category is not Category.PROBE_POOL)
        }

    def unconditioned(self) -> list[JsonValue]:
        """Claim nodes stating no explicit refutation condition anywhere in their text."""
        return [
            node.name
            for node in self.nodes.canonical()
            if node.front.category is not Category.PROBE_POOL and not node.conditioned
        ]

    def unjudged_sketches(self) -> dict[str, JsonValue]:
        """Sketched nodes whose counsel standing is absent, missing, or names no rung.

        A node whose `judgments/<node>.ndjson` holds a recorded ruling has standing that
        is machine-checkable and answers here directly, whoever ruled and however hard
        it cut, because the question is whether counsel ruled at all rather than whether
        the claim survived. A node with none falls back to the frontmatter pointers and
        a regex over the prose behind them, which is what the record looked like before
        rulings were recorded as data.
        """
        report: dict[str, JsonValue] = {}
        for node in self.nodes.canonical():
            standing = RulingLedger(node.directory).read(node.name)
            if node.status is not Status.SKETCHED or standing:
                continue
            troubles = [
                trouble
                for pointer in node.front.judgments
                if (trouble := self.__ruled(node, pointer))
            ] or (["no judgment linked in the frontmatter"] if not node.front.judgments else [])
            if troubles:
                report[node.name] = list[JsonValue](troubles)
        return report

    def unstated(self) -> list[JsonValue]:
        """Claim nodes whose statement of record is empty or placeholder-only."""
        return [
            node.name
            for node in self.nodes.canonical()
            if node.front.category is not Category.PROBE_POOL and not node.stated
        ]

    def __ruled(self, node: Node, pointer: str) -> str:
        """What is wrong with one linked judgment, empty when it exists and names a rung.

        node: the sketched node linking the judgment.
        pointer: the judgment path, node-directory-relative or workspace-root-relative.
        """
        path = node.directory / pointer
        if not path.exists():
            path = self.root / pointer
        if not path.exists():
            return f"judgment {pointer} does not exist"
        if not _RUNG.search(path.read_text(encoding="utf-8")):
            return f"judgment {pointer} names no attacking rung"
        return ""

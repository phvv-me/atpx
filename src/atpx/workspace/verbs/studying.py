import re
from pathlib import Path

from ...blueprint.manifest import Blueprint
from ...briefing.brief import Briefing
from ...briefing.judge import JudgeBriefing
from ...core import git_revision
from ...graph.journal import LogEntry
from ...graph.node import Node
from ...study.designing import Design
from ...support.clock import today
from ..foundation import Slug, TagName
from ..state import FoundationState

_TAG = re.compile(r"^[\w.-]+$")


class StudyVerbs(FoundationState):
    """The read-and-annotate verbs: briefs, fleet views, the journal, and the index.

    The lint is not here: `doctor` answers for a whole tree of workspaces at once, so it
    lives on the facade that knows how to open one.
    """

    def adopt(self, slug: Slug, source: str) -> str:
        """Copy a markdown note into `blueprints/<slug>/node.md`, never deleting the source.

        The import verb for statements written elsewhere, an AIZK export, a
        draft, a legacy note. A `blueprint:` frontmatter line is stripped,
        redundant once the node lives inside its blueprint directory.

        slug: the blueprint directory name the node moves into, created when missing.
        source: path to the markdown file to adopt.
        """
        note = Path(source)
        if not note.exists():
            raise FileNotFoundError(
                f"no note at {note}; pass --source pointing at a markdown file"
            )
        lines = [
            line for line in note.read_text().splitlines() if not line.startswith("blueprint:")
        ]
        target = self.blueprints / slug / Node.FILENAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n")
        return str(target.relative_to(self.root))

    def brief(self, slug: Slug) -> str:
        """The full agent context bundle for one blueprint node, as markdown.

        slug: the blueprint directory name under the blueprints root.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        node = self.nodes.find(slug)
        return Briefing(blueprint, node, self.nodes, git_revision(self.root)).render()

    def design(self, slug: Slug) -> str:
        """Scaffold today's pre-registration file for one node, allocating its seed base.

        An AsPredicted-shaped `design-<date>.md` lands in the node directory
        with hypothesis, observable, conditions, decision rule, cost estimate,
        and exploratory declaration to fill in before the run, and the seed
        base it quotes is drawn fresh from the workspace-wide frontmatter
        registry and recorded in the node's `seeds` list in the same call.

        slug: the blueprint directory name holding the node.
        """
        return str(Design(self.nodes).scaffold(slug).relative_to(self.root))

    def graph(self) -> list[dict[str, str | dict[str, str] | dict[str, list[str]]]]:
        """The frontier: unsettled nodes whose wikilink dependencies are all settled."""
        return self.nodes.frontier()

    def index(self) -> str:
        """Regenerate the index artifacts from node state, returning the markdown.

        Writes both files the workspace's `index` setting anchors: the INDEX
        note with its generated table, and the blueprint-shaped graph JSON
        beside it. Hand-authored prose survives under the manual section, moved
        there whole the first time the generator meets a hand-written index.
        """
        return self.ledger_index.write(self.nodes.nodes())

    def judge_brief(self, slug: Slug) -> str:
        """What changed since the node's last judgment snapshot, as markdown.

        slug: the blueprint directory name under the blueprints root.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        node = self.nodes.find(slug)
        return JudgeBriefing(blueprint, node).render()

    def log(self, slug: Slug, who: str, tag: TagName, message: str) -> str:
        """Append one journal line to a node, `- [who/tag date] message`.

        Status moves live in `settle`, which gates them on evidence. The entry
        is validated to round-trip through the journal parser, so a `who` with
        spaces or a multi-line message is refused instead of silently vanishing.

        slug: the blueprint directory name holding the node.
        who: free-form author label, mathematician, prover, refuter, a model name.
        tag: the strategy or pass tag inside the brackets.
        message: the one-line entry body.
        """
        node = self.nodes.find(slug)
        line = str(LogEntry.today(who=who, tag=tag, message=message))
        node.append_log(line)
        return line

    def note(self, slug: Slug, text: str, *, tag: TagName = "note") -> str:
        """Append one dated evidence bullet to a node, `- [tag date] text`, append-only.

        The bullet lands at the end of the `## Evidence` section, stamped with
        today's UTC date. Nothing above that heading is ever touched: a node
        without an `## Evidence` section is refused rather than restructured,
        statement and frontmatter included.

        slug: the blueprint directory name holding the node.
        text: the one-line evidence bullet body.
        tag: the pass or source tag inside the brackets.
        """
        if not _TAG.match(tag):
            raise ValueError(f"tag {tag!r} must match {_TAG.pattern}")
        if "".join(text.splitlines()) != text:
            raise ValueError("an evidence bullet must stay on one line")
        node = self.nodes.find(slug)
        line = f"- [{tag} {today()}] {text}"
        node.append_evidence(line)
        return line

    def status(self) -> dict[str, list[str]]:
        """Node names grouped by status, malformed or absent values under `invalid`."""
        return self.nodes.statuses()

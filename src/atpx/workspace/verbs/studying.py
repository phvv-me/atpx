from pathlib import Path

from ...blueprint.manifest import Blueprint
from ...briefing.brief import Briefing
from ...briefing.judge import JudgeBriefing
from ...core import git_revision
from ...graph.journal import LogEntry
from ...graph.node import Node
from ..foundation import Slug, TagName
from ..state import FoundationState


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

    def graph(self) -> list[dict[str, str | dict[str, str] | dict[str, list[str]]]]:
        """The frontier: unsettled nodes whose wikilink dependencies are all settled."""
        return self.nodes.frontier()

    def index(self, *, write: bool = False) -> str:
        """Regenerate the results index from node frontmatter, writing it when asked.

        write: persist the regenerated index over the existing file.
        """
        text = self.results_index.render(self.nodes.nodes())
        if write:
            self.results_index.path.write_text(text)
        return text

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

    def status(self) -> dict[str, list[str]]:
        """Node names grouped by status, malformed or absent values under `invalid`."""
        return self.nodes.statuses()

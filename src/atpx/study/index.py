from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from ..graph.node import Node
from ..graph.status import Status


class ResultsIndex:
    """Regenerates the results index note from node frontmatter.

    The prose preamble and footer of the existing file are preserved verbatim;
    only the status sections between them are rebuilt, each entry rendered from
    a node's `summary` frontmatter.
    """

    SECTIONS: ClassVar[list[tuple[set[Status], str]]] = [
        ({Status.VERIFIED}, "## Verified (Lean-checked)"),
        ({Status.VALIDATED}, "## Validated (rigorous machine certificate)"),
        ({Status.SKETCHED}, "## Sketched (refuter-survived, usable)"),
        ({Status.IN_PROGRESS, Status.OPEN}, "## In progress / open"),
        ({Status.REFUTED}, "## Refuted"),
        ({Status.KNOWN}, "## Known (already in the literature)"),
        ({Status.ABANDONED}, "## Abandoned"),
    ]

    def __init__(self, path: Path) -> None:
        """path: the index markdown file, which may not exist yet."""
        self.path = path

    def entry(self, node: Node) -> str:
        """One index list line for a node; the slug names the blueprint directory."""
        return f"- [[{node.name}]], {node.summary}."

    def render(self, nodes: Sequence[Node]) -> str:
        """The full regenerated index text.

        nodes: every blueprint node the store tracks.
        """
        preamble, footer = self.surroundings()
        blocks = [preamble]
        for statuses, heading in self.SECTIONS:
            group = [node for node in nodes if node.status in statuses]
            if not group:
                continue
            group.sort(key=lambda node: node.name)
            group.sort(key=lambda node: node.date, reverse=True)
            blocks.append(heading + "\n\n" + "\n".join(map(self.entry, group)))
        if footer:
            blocks.append(footer)
        return "\n\n".join(blocks) + "\n"

    def surroundings(self) -> tuple[str, str]:
        """The preserved (preamble, footer) prose around the generated sections."""
        if not self.path.exists():
            return f"# {self.path.stem}", ""
        lines = self.path.read_text().splitlines()
        first_heading = next(
            (i for i, line in enumerate(lines) if line.startswith("## ")), len(lines)
        )
        preamble = "\n".join(lines[:first_heading]).strip()
        last_entry = max(
            (i for i, line in enumerate(lines) if line.startswith("- ")), default=len(lines)
        )
        footer = "\n".join(lines[last_entry + 1 :]).strip()
        return preamble, footer

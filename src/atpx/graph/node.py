import re
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from .journal import LogEntry
from .status import Status

_WIKILINK = re.compile(r"\[\[([^\]|#]+)")
_TAG = re.compile(r"(?<!\S)#([\w-]+)")
_LOG_HEADING = "## Log"
_LOG_LINE = re.compile(r"^- \[(\w+)/([\w.-]+) (\d{4}-\d{2}-\d{2})\] (.*)$", re.MULTILINE)


class Node:
    """One proof node backed by `node.md` inside its blueprint directory.

    The blueprint directory is the unit of mathematical state: statement,
    status, and journal live in `node.md` next to the runnable evidence, and
    the node's name is the directory name, the slug wikilinks reference.
    """

    FILENAME: ClassVar[str] = "node.md"

    def __init__(self, path: Path) -> None:
        """path: the `node.md` file inside a blueprint directory."""
        self.path = path

    @property
    def date(self) -> str:
        """ISO date from the frontmatter, empty when absent."""
        return self.frontmatter.get("date", "")

    @property
    def directory(self) -> Path:
        """The blueprint directory holding this node and its evidence."""
        return self.path.parent

    @property
    def frontmatter(self) -> dict[str, str]:
        """The YAML-ish key value block between the leading `---` fences."""
        lines = self.text.splitlines()
        if not lines or lines[0] != "---":
            return {}
        fields = {}
        for line in lines[1:]:
            if line == "---":
                break
            key, separator, value = line.partition(": ")
            if separator:
                fields[key.strip()] = value.strip()
        return fields

    @property
    def links(self) -> list[str]:
        """Wikilink targets in order of appearance, duplicates removed."""
        return list(dict.fromkeys(_WIKILINK.findall(self.text)))

    @property
    def log(self) -> list[LogEntry]:
        """Every journal line in file order, anything not in the house format skipped."""
        return [
            LogEntry(who=who, tag=tag, date=date, message=message)
            for who, tag, date, message in _LOG_LINE.findall(self.text)
        ]

    @property
    def name(self) -> str:
        """The node's identity, its blueprint directory name, which wikilinks reference."""
        return self.path.parent.name

    @property
    def raw_status(self) -> str | None:
        """The literal frontmatter status string, None when the node carries none."""
        return self.frontmatter.get("status") or None

    RELATIONS: ClassVar[tuple[str, ...]] = ("successor_of", "refutes", "shadows", "lemma_for")

    @property
    def relations(self) -> dict[str, list[str]]:
        """Typed edges from flat frontmatter keys, each a comma-separated slug list.

        The lineage the campaigns used to narrate in journal prose, made
        computable: `successor_of` points at the node this one grew from,
        `refutes` at what its counterexample killed, `shadows` at nodes whose
        certificates its findings weaken, `lemma_for` at the nodes that lean
        on it.
        """
        found = {}
        for kind in self.RELATIONS:
            raw = self.frontmatter.get(kind, "")
            slugs = [part.strip() for part in raw.split(",") if part.strip()]
            if slugs:
                found[kind] = slugs
        return found

    @property
    def status(self) -> Status | None:
        """The node's lifecycle status, None when absent or not a known value.

        Readers stay tolerant by design: an agent-invented status string must
        never crash a fleet view, `doctor` reports it instead.
        """
        value = self.raw_status
        try:
            return Status(value) if value else None
        except ValueError:
            return None

    @property
    def summary(self) -> str:
        """One-line result summary the index entry shows, empty when absent."""
        return self.frontmatter.get("summary", "")

    @property
    def tags(self) -> set[str]:
        """Every #tag in the node body."""
        return set(_TAG.findall(self.text))

    @property
    def text(self) -> str:
        """Current file content."""
        return self.path.read_text()

    def append_log(self, line: str) -> None:
        """Append one formatted line to the `## Log` section, creating it when missing.

        line: the already formatted `- [who/tag date] message` entry.
        """
        lines = self.text.splitlines()
        start = next((i for i, text in enumerate(lines) if text.startswith(_LOG_HEADING)), None)
        if start is None:
            lines += ["", f"{_LOG_HEADING}    (append-only: [who/tag YYYY-MM-DD] one line)"]
            start = len(lines) - 1
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines)
        )
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, line)
        self.path.write_text("\n".join(lines) + "\n")

    def set_status(self, status: Status) -> None:
        """Rewrite the frontmatter `status` field, the node's one mutable field.

        Edits the field in place when the node already carries a frontmatter block,
        inserts it just inside the opening fence when the block has no status line, and
        opens a fresh frontmatter block when the node has none. Reading tolerates a node
        whose closing fence is missing (see :attr:`frontmatter`), so writing must too
        rather than raise on the same malformed file.

        status: the new lifecycle status.
        """
        lines = self.text.splitlines()
        field = f"status: {status.value}"
        if not lines or lines[0] != "---":
            lines[:0] = ["---", field, "---", ""]
            self.path.write_text("\n".join(lines) + "\n")
            return
        fence = self.__closing_fence(lines)
        for position in range(1, fence):
            if lines[position].startswith("status:"):
                lines[position] = field
                break
        else:
            lines.insert(1, field)
        self.path.write_text("\n".join(lines) + "\n")

    @staticmethod
    def __closing_fence(lines: Sequence[str]) -> int:
        """Index of the frontmatter's closing `---`, or the line count when it is absent.

        A node that opens a frontmatter block but never closes it still has every line
        after the opening fence treated as frontmatter, the same lenient reading
        :attr:`frontmatter` does, so a status edit never raises on a half-written file.
        """
        try:
            return lines.index("---", 1)
        except ValueError:
            return len(lines)

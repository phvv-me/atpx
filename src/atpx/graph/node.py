import re
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from .frontmatter import Frontmatter, fields, split_slugs
from .journal import LogEntry
from .status import Status

_WIKILINK = re.compile(r"\[\[([^\]|#]+)")
_TAG = re.compile(r"(?<!\S)#([\w-]+)")
_LOG_HEADING = "## Log"
_LOG_LINE = re.compile(r"^- \[(\w+)/([\w.-]+) (\d{4}-\d{2}-\d{2})\] (.*)$", re.MULTILINE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def statement_of(text: str) -> str:
    """The statement of record inside one node text, empty when it has none.

    The `## Statement` section when the node declares one, else everything
    between the title heading and the first section heading, the implicit
    statement block of the pre-contract ledger. The same extraction reads a
    live node and a judgment snapshot, so the drift lint compares like with
    like.

    text: the full node or snapshot content.
    """
    lines = text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.lower().startswith("## statement")),
        next((i for i, line in enumerate(lines) if line.startswith("# ")), None),
    )
    if start is None:
        return ""
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start + 1 : end]).strip()


class Node:
    """One proof node backed by `node.md` inside its blueprint directory.

    The blueprint directory is the unit of mathematical state: statement,
    status, and journal live in `node.md` next to the runnable evidence, and
    the node's name is the directory name, the slug wikilinks reference.
    """

    FILENAME: ClassVar[str] = "node.md"
    EVIDENCE_HEADINGS: ClassVar[tuple[str, ...]] = ("## Evidence", "## Ledger")

    def __init__(self, path: Path) -> None:
        """path: the `node.md` file inside a blueprint directory."""
        self.path = path

    @property
    def conditioned(self) -> bool:
        """Whether the node states an explicit refutation condition anywhere in its text."""
        return "refutation condition" in self.text.lower()

    @property
    def date(self) -> str:
        """ISO date from the frontmatter, empty when absent."""
        return self.frontmatter.get("date", "")

    @property
    def directory(self) -> Path:
        """The blueprint directory holding this node and its evidence."""
        return self.path.parent

    @property
    def front(self) -> Frontmatter:
        """The typed frontmatter contract, tolerant of backfill gaps."""
        return Frontmatter.parse(self.text)

    @property
    def frontmatter(self) -> dict[str, str]:
        """The YAML-ish key value block between the leading `---` fences."""
        return fields(self.text) or {}

    @property
    def headline(self) -> str:
        """The title heading's text, the one-line claim the index quotes."""
        found = re.search(r"^# (.+)$", self.text, re.MULTILINE)
        return found.group(1).strip() if found else ""

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

    RELATIONS: ClassVar[tuple[str, ...]] = Frontmatter.RELATIONS

    @property
    def relations(self) -> dict[str, list[str]]:
        """Typed edges from flat frontmatter keys, each a comma-separated slug list.

        The lineage the campaigns used to narrate in journal prose, made
        computable: `successor_of` points at the node this one grew from,
        `refutes` at what its counterexample killed, `shadows` at nodes whose
        certificates its findings weaken, `lemma_for` at the nodes that lean
        on it, and `superseded_by` at the node of record a stub now points to.
        A null spelling or an implausible value never joins the slugs `split_slugs`
        returns, so it can never mint a phantom edge; `doctor` reports it instead.
        """
        found = {}
        for kind in self.RELATIONS:
            slugs, _ = split_slugs(self.frontmatter.get(kind, ""))
            if slugs:
                found[kind] = slugs
        return found

    @property
    def root(self) -> str:
        """The blueprints root this node was found under, its directory's parent's name."""
        return self.path.parent.parent.name

    @property
    def stated(self) -> bool:
        """Whether the statement of record holds real prose, placeholders aside."""
        return bool(_COMMENT.sub("", self.statement).strip())

    @property
    def statement(self) -> str:
        """The statement of record, per `statement_of`."""
        return statement_of(self.text)

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
    def superseded(self) -> bool:
        """Whether this node is a pointer whose claim of record lives somewhere else."""
        return bool(self.superseded_by)

    @property
    def superseded_by(self) -> str:
        """Where the node of record moved to, empty for a node that is still its own record.

        The pointer is a slug or a `<root>/<slug>` path, since a migration that
        moves a claim between blueprint roots leaves the stub behind naming both.
        A null spelling or an implausible value reads as no pointer at all, the
        same as the key being absent.
        """
        slugs, _ = split_slugs(self.frontmatter.get("superseded_by", ""))
        return slugs[0] if slugs else ""

    @property
    def tags(self) -> set[str]:
        """Every #tag in the node body."""
        return set(_TAG.findall(self.text))

    @property
    def text(self) -> str:
        """Current file content."""
        return self.path.read_text()

    def append_evidence(self, line: str) -> None:
        """Append one bullet at the end of the evidence section, and nowhere else.

        `## Evidence` and `## Ledger` are two spellings of one section, so a node
        that calls its readings a ledger is written to exactly like one that calls
        them evidence. Evidence is append-only below the statement, so a node with
        neither heading is refused rather than restructured: nothing this method
        writes can ever touch a line above it.

        line: the already formatted `- [tag date] text` bullet.
        """
        lines = self.text.splitlines()
        start = next(
            (i for i, text in enumerate(lines) if text.startswith(self.EVIDENCE_HEADINGS)), None
        )
        if start is None:
            headings = " or ".join(repr(heading) for heading in self.EVIDENCE_HEADINGS)
            raise ValueError(
                f"{self.name} has no {headings} section; "
                "add one below the statement before noting evidence"
            )
        self.path.write_text("\n".join(self.__inserted(lines, start, line)) + "\n")

    def append_log(self, line: str) -> None:
        """Append one formatted line to the `## Log` section, creating it when missing.

        line: the already formatted `- [who/tag date] message` entry.
        """
        lines = self.text.splitlines()
        start = next((i for i, text in enumerate(lines) if text.startswith(_LOG_HEADING)), None)
        if start is None:
            lines += ["", f"{_LOG_HEADING}    (append-only: [who/tag YYYY-MM-DD] one line)"]
            start = len(lines) - 1
        self.path.write_text("\n".join(self.__inserted(lines, start, line)) + "\n")

    def set_field(self, key: str, *, value: str) -> None:
        """Rewrite one frontmatter field in place, opening a block when the node has none.

        Edits the field's line when the block already carries it, inserts it just inside
        the opening fence otherwise, and opens a fresh frontmatter block on a plain note.
        Reading tolerates a node whose closing fence is missing (see :func:`fields`), so
        writing must too rather than raise on the same malformed file.

        key: the frontmatter key to write.
        value: the field's new raw text.
        """
        lines = self.text.splitlines()
        field = f"{key}: {value}"
        if not lines or lines[0] != "---":
            lines[:0] = ["---", field, "---", ""]
            self.path.write_text("\n".join(lines) + "\n")
            return
        fence = self.__closing_fence(lines)
        for position in range(1, fence):
            if lines[position].startswith(f"{key}:"):
                lines[position] = field
                break
        else:
            lines.insert(1, field)
        self.path.write_text("\n".join(lines) + "\n")

    def set_status(self, status: Status) -> None:
        """Rewrite the frontmatter `status` field, the lifecycle's one mutable field.

        status: the new lifecycle status.
        """
        self.set_field("status", value=status.value)

    @staticmethod
    def __closing_fence(lines: Sequence[str]) -> int:
        """Index of the frontmatter's closing `---`, or the line count when it is absent."""
        try:
            return lines.index("---", 1)
        except ValueError:
            return len(lines)

    @staticmethod
    def __inserted(lines: Sequence[str], start: int, line: str) -> list[str]:
        """The node lines with one entry appended at the end of the section at `start`.

        lines: the node file's lines.
        start: the index of the section's heading line.
        line: the entry to insert before the next section or the trailing blanks.
        """
        found = list(lines)
        end = next(
            (i for i in range(start + 1, len(found)) if found[i].startswith("## ")), len(found)
        )
        while end > start + 1 and not found[end - 1].strip():
            end -= 1
        found.insert(end, line)
        return found

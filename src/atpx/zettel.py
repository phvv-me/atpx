import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ConfigDict, Field, field_validator

from .base import FrozenModel
from .roles import SETTLED, Status

WIKILINK = re.compile(r"\[\[([^\]|#]+)")
TAG = re.compile(r"(?<!\S)#([\w-]+)")
LOG_HEADING = "## Log"
LOG_LINE = re.compile(r"^- \[(\w+)/([\w.-]+) (\d{4}-\d{2}-\d{2})\] (.*)$", re.MULTILINE)


class LogEntry(FrozenModel):
    """One append-only journal line, `- [who/tag date] message`, validated to round-trip.

    The field constraints mirror `LOG_LINE`, so any entry this model accepts
    is an entry the parser reads back: a `who` with spaces or a message
    holding a line break is refused at write time instead of silently
    vanishing from every later read of the log. The patterns compile on
    Python's `re` so acceptance matches the parser exactly, character class
    semantics included.
    """

    model_config = ConfigDict(regex_engine="python-re")

    who: str = Field(pattern=r"^\w+$")
    tag: str = Field(pattern=r"^[\w.-]+$")
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    message: str

    @field_validator("message")
    @classmethod
    def one_line(cls, value: str) -> str:
        """Refuse messages that would break the one-line journal format."""
        if "".join(value.splitlines()) != value:
            raise ValueError("a journal message must stay on one line")
        return value

    @classmethod
    def today(cls, who: str, tag: str, message: str) -> LogEntry:
        """A validated entry dated today in UTC, the same clock certificates stamp.

        who: free-form author label, one word.
        tag: the strategy or pass tag inside the brackets.
        message: the one-line entry body.
        """
        return cls(who=who, tag=tag, date=datetime.now(UTC).date().isoformat(), message=message)

    def __str__(self) -> str:
        return f"- [{self.who}/{self.tag} {self.date}] {self.message}"


class Zettel:
    """One vault note backed by one markdown file, the unit of mathematical state."""

    def __init__(self, path: Path) -> None:
        """path: the markdown file holding the note."""
        self.path = path

    @property
    def name(self) -> str:
        """The note's identity, its filename stem, which wikilinks reference."""
        return self.path.stem

    @property
    def text(self) -> str:
        """Current file content."""
        return self.path.read_text()

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
    def raw_status(self) -> str | None:
        """The literal frontmatter status string, None when the note carries none."""
        return self.frontmatter.get("status") or None

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
    def date(self) -> str:
        """ISO date from the frontmatter, empty when absent."""
        return self.frontmatter.get("date", "")

    @property
    def summary(self) -> str:
        """One-line result summary the index entry shows, empty when absent."""
        return self.frontmatter.get("summary", "")

    @property
    def blueprint(self) -> str:
        """Path of the blueprint directory holding runnable evidence, empty when absent."""
        return self.frontmatter.get("blueprint", "")

    @property
    def tags(self) -> frozenset[str]:
        """Every #tag in the note body."""
        return frozenset(TAG.findall(self.text))

    @property
    def is_math_node(self) -> bool:
        """Whether this note is a proof node the math loop tracks.

        Keyed on the raw status so a node with a malformed value still shows up
        in fleet views (under `invalid`) instead of silently vanishing.
        """
        return {"math", "proof"} <= self.tags and self.raw_status is not None

    @property
    def links(self) -> list[str]:
        """Wikilink targets in order of appearance, duplicates removed."""
        return list(dict.fromkeys(WIKILINK.findall(self.text)))

    @property
    def log(self) -> list[LogEntry]:
        """Every journal line in file order, anything not in the house format skipped."""
        return [
            LogEntry(who=who, tag=tag, date=date, message=message)
            for who, tag, date, message in LOG_LINE.findall(self.text)
        ]

    def set_status(self, status: Status) -> None:
        """Rewrite the frontmatter `status` field, the note's one mutable field.

        Edits the field in place when the note already carries a frontmatter block,
        inserts it just inside the opening fence when the block has no status line, and
        opens a fresh frontmatter block when the note has none. Reading tolerates a note
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
    def __closing_fence(lines: list[str]) -> int:
        """Index of the frontmatter's closing `---`, or the line count when it is absent.

        A note that opens a frontmatter block but never closes it still has every line
        after the opening fence treated as frontmatter, the same lenient reading
        :attr:`frontmatter` does, so a status edit never raises on a half-written file.
        """
        try:
            return lines.index("---", 1)
        except ValueError:
            return len(lines)

    def append_log(self, line: str) -> None:
        """Append one formatted line to the `## Log` section, creating it when missing.

        line: the already formatted `- [who/tag date] message` entry.
        """
        lines = self.text.splitlines()
        try:
            start = next(i for i, text in enumerate(lines) if text.startswith(LOG_HEADING))
        except StopIteration:
            lines += ["", f"{LOG_HEADING}    (append-only: [who/tag YYYY-MM-DD] one line)"]
            start = len(lines) - 1
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines)
        )
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, line)
        self.path.write_text("\n".join(lines) + "\n")


class Vault:
    """The Zettelkasten directory seen as a graph of proof nodes."""

    def __init__(self, path: Path) -> None:
        """path: the directory of markdown notes."""
        self.path = path

    def notes(self) -> list[Zettel]:
        """Every note in the vault, sorted by name."""
        return [Zettel(p) for p in sorted(self.path.glob("*.md"))]

    def nodes(self) -> list[Zettel]:
        """Every `#math #proof` node with a status."""
        return [note for note in self.notes() if note.is_math_node]

    def find(self, name: str) -> Zettel:
        """The note called `name`, raising with the known names on a miss.

        name: the filename stem a wikilink would use.
        """
        note = Zettel(self.path / f"{name}.md")
        if not note.path.exists():
            known = ", ".join(z.name for z in self.nodes())
            raise KeyError(f"no note named {name!r}; math nodes are {known}")
        return note

    def statuses(self) -> dict[str, list[str]]:
        """Node names grouped by status, ordered down the certification ladder.

        Nodes carrying a status string outside the ladder land in an `invalid`
        bucket with the offending value, never an exception.
        """
        nodes = self.nodes()
        groups = {
            status.value: names
            for status in Status
            if (names := sorted(node.name for node in nodes if node.status is status))
        }
        invalid = sorted(
            f"{node.name} ({node.raw_status})" for node in nodes if node.status is None
        )
        if invalid:
            groups["invalid"] = invalid
        return groups

    def frontier(self) -> list[dict[str, str | dict[str, str]]]:
        """Open or in-progress nodes whose in-vault dependencies are all settled.

        The leanblueprint frontier idea over wikilinks: these are the nodes ready
        to be worked next.
        """
        nodes = {node.name: node for node in self.nodes()}
        ready = []
        for node in nodes.values():
            if node.status in SETTLED:
                continue
            others = [link for link in node.links if link in nodes and link != node.name]
            dependencies = {link: nodes[link].status for link in others}
            if all(status in SETTLED for status in dependencies.values()):
                entry: dict[str, str | dict[str, str]] = {
                    "node": node.name,
                    "status": str(node.status),
                    "deps": {name: str(status) for name, status in dependencies.items()},
                }
                ready.append(entry)
        return ready

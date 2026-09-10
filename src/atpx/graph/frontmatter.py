import re
from datetime import datetime
from typing import ClassVar

from patos import FrozenModel

from .category import Category

_MISSING = "no frontmatter block"
_NULL_FAMILY = {"null", "~", "none"}
_IMPLAUSIBLE = re.compile(r"[\s:]")


def fields(text: str) -> dict[str, str] | None:
    """The raw `key: value` pairs between the leading `---` fences, None without a block.

    The one tolerant scan every frontmatter reader shares: lines outside the
    house `key: value` shape are skipped, and a block whose closing fence is
    missing reads to the end of the file.

    text: the full node file content.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None
    found = {}
    for line in lines[1:]:
        if line == "---":
            break
        key, separator, value = line.partition(": ")
        if separator:
            found[key.strip()] = value.strip()
    return found


def split_slugs(raw: str) -> tuple[list[str], list[str]]:
    """One field's raw comma list split into its real slugs and its implausible items.

    A null-family spelling (`null`, `~`, `none`/`None`) or an empty item names no
    slug and is silently absent, the same as the key being missing outright.
    Anything else that cannot be a real slug either (whitespace, a colon inside
    it) is absent too, but named in the second list, so `successor_of: null`
    reads as no predecessor rather than minting the literal word as a graph
    edge, while a value that is broken some other way still gets named for
    `doctor` to report.

    raw: the field's raw text after the key.
    """
    found = []
    implausible = []
    for item in Frontmatter.listed(raw):
        if item.lower() in _NULL_FAMILY or _IMPLAUSIBLE.search(item):
            implausible.append(item)
        else:
            found.append(item)
    return found, implausible


class Frontmatter(FrozenModel):
    """The typed node.md frontmatter contract, read tolerantly for backfill.

    Every field is optional because the ledger predates the contract: a missing
    block or a malformed field lands in `problems` for `doctor` to report, and
    never raises.

    The Open Knowledge Format supplies the catalog half: `type` is its one
    required key and says what the node is (`experiment`, `theorem`,
    `conjecture`), with the house's older `kind` read as its spelling so a node
    written before the format still types itself, and `title`, `description`,
    `resource`, `tags`, `timestamp`, `generated`, `verified`, `sources`,
    `stale_after`, and `okf_version` are its optional keys, read as written and
    flagged by nothing, so an OKF reader and this one see one catalog entry.
    `status` is the exception the two formats share by name only: the ledger's
    lifecycle ladder is the vocabulary that governs here, never OKF's own
    draft/stable/deprecated, so nothing validates it against theirs. A key whose
    value OKF writes as an indented block is carried as the text on the key's own
    line, since the frontmatter scan every reader shares is flat by design; the
    file itself is never rewritten wholesale, so the block survives on disk.

    The ledger half is the graph: `aliases` names the spellings this node still
    answers to after a rename, `depends` the slugs the statement leans on,
    `serves` the papers or experiments the node feeds, `seeds` the seed bases
    allocated to this node (the workspace-wide registry `design` draws from),
    `judgments` the ruling files a sketched status rests on, and `superseded_by`
    the node of record a stub now defers to, a slug or a `<root>/<slug>` pointer.
    """

    status: str | None = None
    type: str | None = None
    title: str = ""
    description: str = ""
    resource: str = ""
    tags: list[str] = []
    timestamp: str = ""
    generated: str = ""
    verified: str = ""
    sources: list[str] = []
    stale_after: str = ""
    okf_version: str = ""
    aliases: list[str] = []
    depends: list[str] = []
    serves: list[str] = []
    seeds: list[int] = []
    judgments: list[str] = []
    superseded_by: str = ""
    problems: list[str] = []

    RELATIONS: ClassVar[tuple[str, ...]] = (
        "successor_of",
        "refutes",
        "shadows",
        "lemma_for",
        "superseded_by",
    )

    @property
    def category(self) -> Category:
        """The node's category, `claim` for every type that is not a special one."""
        normalized = (self.type or "").replace("-", "_")
        try:
            return Category(normalized)
        except ValueError:
            return Category.CLAIM

    @property
    def present(self) -> bool:
        """Whether the node carries a frontmatter block at all."""
        return _MISSING not in self.problems

    @classmethod
    def listed(cls, value: str) -> list[str]:
        """A frontmatter list value, `[a, b]` or bare `a, b`, as its items.

        value: the raw field text after the key.
        """
        inner = value.strip().removeprefix("[").removesuffix("]")
        return [item for part in inner.split(",") if (item := part.strip().strip("'\""))]

    @classmethod
    def parse(cls, text: str) -> Frontmatter:
        """Read one node file's frontmatter into the contract, collecting problems.

        Every slug-valued key, `aliases`, `depends`, `serves`, `superseded_by`, and
        the four edge keys `Node.relations` reads, is screened by `split_slugs`: a
        null spelling never mints a graph edge, and anything else unslug-like is
        named in `problems` instead. `kind` is read as an older spelling of `type`,
        so the format migration never has to be finished before the ledger reads.

        text: the full node file content.
        """
        raw = fields(text)
        if raw is None:
            return cls(problems=[_MISSING])
        problems = []
        seeds = []
        for item in cls.listed(raw.get("seeds", "")):
            if item.lower() in _NULL_FAMILY:
                continue
            try:
                seeds.append(int(item))
            except ValueError:
                problems.append(f"seeds entry {item!r} is not an integer")
        slugs = {}
        for key in dict.fromkeys(("aliases", "depends", "serves", *cls.RELATIONS)):
            slugs[key], bad = split_slugs(raw.get(key, ""))
            problems += [f"{key} entry {item!r} is not a plausible slug" for item in bad]
        timestamp = raw.get("timestamp", "")
        problems += cls.__misread(timestamp)
        superseded = slugs["superseded_by"]
        return cls(
            status=raw.get("status") or None,
            type=raw.get("type") or raw.get("kind") or None,
            title=raw.get("title", ""),
            description=raw.get("description", ""),
            resource=raw.get("resource", ""),
            tags=cls.listed(raw.get("tags", "")),
            timestamp=timestamp,
            generated=raw.get("generated", ""),
            verified=raw.get("verified", ""),
            sources=cls.listed(raw.get("sources", "")),
            stale_after=raw.get("stale_after", ""),
            okf_version=raw.get("okf_version", ""),
            aliases=slugs["aliases"],
            depends=slugs["depends"],
            serves=slugs["serves"],
            seeds=seeds,
            judgments=cls.listed(raw.get("judgments", "")),
            superseded_by=superseded[0] if superseded else "",
            problems=problems,
        )

    @staticmethod
    def __misread(timestamp: str) -> list[str]:
        """The problem an unreadable OKF timestamp raises, none for a blank or ISO 8601 one."""
        if not timestamp:
            return []
        try:
            datetime.fromisoformat(timestamp)
        except ValueError:
            return [f"timestamp {timestamp!r} is not ISO 8601"]
        return []

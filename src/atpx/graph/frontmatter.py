import re
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
    never raises. `depends` names the slugs the statement leans on, `serves`
    the papers or experiments the node feeds, `seeds` the seed bases allocated
    to this node (the workspace-wide registry `design` draws from), `judgments`
    the ruling files a sketched status rests on, and `superseded_by` the node
    of record a stub now defers to, a slug or a `<root>/<slug>` pointer.
    """

    status: str | None = None
    kind: str | None = None
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
        """The node's category, `claim` for every kind that is not a special one."""
        normalized = (self.kind or "").replace("-", "_")
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

        Every slug-valued key, `depends`, `serves`, `superseded_by`, and the four
        edge keys `Node.relations` reads, is screened by `split_slugs`: a null
        spelling never mints a graph edge, and anything else unslug-like is named
        in `problems` instead.

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
        depends, bad = split_slugs(raw.get("depends", ""))
        problems += [f"depends entry {item!r} is not a plausible slug" for item in bad]
        serves, bad = split_slugs(raw.get("serves", ""))
        problems += [f"serves entry {item!r} is not a plausible slug" for item in bad]
        superseded, bad = split_slugs(raw.get("superseded_by", ""))
        problems += [f"superseded_by entry {item!r} is not a plausible slug" for item in bad]
        for key in cls.RELATIONS:
            if key == "superseded_by":
                continue
            _, bad = split_slugs(raw.get(key, ""))
            problems += [f"{key} entry {item!r} is not a plausible slug" for item in bad]
        return cls(
            status=raw.get("status") or None,
            kind=raw.get("kind") or None,
            depends=depends,
            serves=serves,
            seeds=seeds,
            judgments=cls.listed(raw.get("judgments", "")),
            superseded_by=superseded[0] if superseded else "",
            problems=problems,
        )

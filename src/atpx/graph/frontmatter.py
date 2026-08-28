from patos import FrozenModel

from .category import Category

_MISSING = "no frontmatter block"


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

        text: the full node file content.
        """
        raw = fields(text)
        if raw is None:
            return cls(problems=[_MISSING])
        problems = []
        seeds = []
        for item in cls.listed(raw.get("seeds", "")):
            try:
                seeds.append(int(item))
            except ValueError:
                problems.append(f"seeds entry {item!r} is not an integer")
        return cls(
            status=raw.get("status") or None,
            kind=raw.get("kind") or None,
            depends=cls.listed(raw.get("depends", "")),
            serves=cls.listed(raw.get("serves", "")),
            seeds=seeds,
            judgments=cls.listed(raw.get("judgments", "")),
            superseded_by=raw.get("superseded_by", ""),
            problems=problems,
        )

import re
from pathlib import Path
from typing import ClassVar

from .status import Status


class ResultDocument:
    """The verdict a node's write-up states, read beside the node document it belongs to.

    A campaign that finished writes its numbers into a result note next to its
    `node.md`, and that note is where a reader learns how the run came out. The two
    can disagree: the ledger has carried a node reading `registered` for a campaign
    whose own result note settled it `validated` days earlier, which makes the index,
    the frontier and every count read the run as still owed. So the note declares its
    verdict on one line, `Status: validated` or `Verdict: refuted`, bold or plain,
    and that word is the only thing read here. Prose that merely mentions a ladder
    word states nothing, so a write-up can never contradict its node by accident.

    The note is named after the node document it settles: `node.md` is settled by
    `result.md` or `results.md`, and a second node document `<name>-node.md` in the
    same blueprint by `<name>-result.md`. One directory can therefore hold several
    registrations, each settled by its own write-up, without either note having to
    say which node it is about.
    """

    NAMES: ClassVar[tuple[str, ...]] = ("result.md", "results.md")
    DECLARED: ClassVar[re.Pattern[str]] = re.compile(
        r"^(?:status|verdict)\s*:\s*\*{0,2}\s*([a-z_]+)", re.IGNORECASE | re.MULTILINE
    )

    def __init__(self, node: Path) -> None:
        """node: the node document whose result note is being read."""
        self.node = node

    @property
    def declared(self) -> str:
        """The raw verdict word the note states, empty when it has none or states none."""
        path = self.path
        if path is None:
            return ""
        found = self.DECLARED.search(path.read_text(encoding="utf-8"))
        return found[1].lower() if found else ""

    @property
    def path(self) -> Path | None:
        """The result note settling this node document, None when it has none."""
        prefix = self.node.name.removesuffix("node.md")
        candidates = (self.node.parent / f"{prefix}{name}" for name in self.NAMES)
        return next((found for found in candidates if found.is_file()), None)

    @property
    def verdict(self) -> Status | None:
        """The declared verdict as a lifecycle status, None when the note declares none.

        A word outside the ladder reads as no declaration rather than as a failure,
        the same tolerance every other reader of a hand-written field extends.
        """
        try:
            return Status(self.declared) if self.declared else None
        except ValueError:
            return None

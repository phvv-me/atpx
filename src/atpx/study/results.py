import re
from pathlib import Path
from typing import ClassVar

_WIKILINK = re.compile(r"\[\[([^\]|#]+)")


class ResultsLedger:
    """The hand-authored results table beside the generated index, read and never written.

    `INDEX.md` lists the program's NODES and this lists its RESULTS: one row per
    finding, carrying the number, the receipt that backs it and the node that measured
    it, so a reader learns what a program holds without opening every node file. The
    generator never touches it, which is exactly why it drifts: a campaign settles, the
    index moves, and the results table keeps the state the program was in last time
    somebody remembered to add a row.

    A row cites its node by wikilink, so the citations are machine-readable and the
    lint can say which settled node the table never got a row for. Nothing here writes:
    the numbers are quoted from the nodes by a person, and a generator that invented
    them would defeat the point of the file.
    """

    NAME: ClassVar[str] = "RESULTS.md"

    def __init__(self, path: Path) -> None:
        """path: the results markdown file, whether or not it exists yet."""
        self.path = path

    @property
    def cited(self) -> set[str]:
        """Every node slug the table links to, empty when there is no table to read."""
        if not self.path.is_file():
            return set()
        return set(_WIKILINK.findall(self.path.read_text(encoding="utf-8")))

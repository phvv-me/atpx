import json
import warnings
from functools import cached_property
from pathlib import Path

from pydantic import JsonValue

from .locking import Guard
from .tearing import TornLedger


class Stream:
    """An append-only NDJSON file, where one torn record costs itself and nothing else.

    Every ledger in this package keeps this shape: one JSON record per line, a write
    that only ever opens the file for append, and a read that warns past whatever it
    cannot decode instead of raising. So a killed process, a full disk, or a record
    whose stored text was truncated damages exactly the record it was writing, while
    everything around it still reads. Two writers on one host are serialized by the
    lock, which is the only way a half-written line can interleave with another.

    Records split on the newline alone and never on `str.splitlines`, which also breaks
    at NEL, the line and paragraph separators, and the vertical tab. JSON escapes none
    of those, so a record carrying one in its text would otherwise tear itself in half
    on the way back in.
    """

    def __init__(self, path: Path) -> None:
        """path: the NDJSON file this stream reads and appends to."""
        self.path = path

    @cached_property
    def guard(self) -> Guard:
        """The lock an append takes, so a caller can widen it around its own read first."""
        return Guard(self.path)

    @property
    def records(self) -> list[tuple[str, JsonValue]]:
        """(where it sits, decoded record) per line, undecodable lines warned away.

        `where` is `<file>:<line>`, which is the whole of what a reader needs to go and
        look at the damage. A file that was never written answers with nothing.
        """
        try:
            text = self.path.read_text()
        except FileNotFoundError:
            return []
        numbered = [
            (f"{self.path}:{number}", line)
            for number, line in enumerate(text.split("\n"), start=1)
            if line.strip()
        ]
        return [
            (where, record)
            for where, line in numbered
            if (record := self.decoded(line, where=where)) is not None
        ]

    @staticmethod
    def decoded(text: str, *, where: str) -> JsonValue | None:
        """One record's JSON, None with a warning when it does not decode.

        text: the record's raw text.
        where: the file and position the record sits at, quoted in the warning.
        """
        try:
            found: JsonValue = json.loads(text)
        except json.JSONDecodeError as error:
            return Stream.skipped(f"{where} does not decode as JSON, skipping it: {error}")
        return found

    @staticmethod
    def skipped(complaint: str) -> None:
        """Warn that one record is unreadable and read on, so the file around it stands.

        complaint: what is wrong and exactly where the record sits.
        """
        warnings.warn(complaint, TornLedger, stacklevel=3)

    def append(self, record: str) -> Path:
        """Append one already-encoded JSON record as its own line, under the lock.

        record: the record's JSON text, without its newline.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.guard, self.path.open("a", encoding="utf-8") as stream:
            stream.write(record + "\n")
        return self.path

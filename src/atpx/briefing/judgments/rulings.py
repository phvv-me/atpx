from pathlib import Path

from pydantic import JsonValue

from ...core.streaming import Stream
from .ruling import Ruling


class RulingLedger:
    """The append-only rulings on one node, `judgments/<node>.ndjson` in a blueprint dir.

    One line per ruling, appended and never rewritten, beside the prose each line
    summarizes. A line that does not decode is skipped with the same `TornLedger`
    warning the evidence stream raises, so one bad line never hides a node's counsel
    standing from the lint that reads it.
    """

    def __init__(self, directory: Path) -> None:
        """directory: the blueprint directory the node's judgments live in."""
        self.directory = directory / "judgments"

    def path(self, node: str) -> Path:
        """Where one node's rulings are recorded."""
        return self.directory / f"{node}.ndjson"

    def read(self, node: str) -> list[Ruling]:
        """Every ruling recorded on a node, oldest first, unreadable lines warned away.

        node: the blueprint directory name the rulings were made against.
        """
        stream = Stream(self.path(node))
        return [
            ruling
            for where, record in stream.records
            if (ruling := self.__ruling(record, where=where)) is not None
        ]

    def record(self, node: str, ruling: Ruling) -> Path:
        """Append one ruling to a node's record.

        node: the blueprint directory name the ruling was made against.
        ruling: the ruling to persist.
        """
        return Stream(self.path(node)).append(ruling.model_dump_json())

    @staticmethod
    def __ruling(record: JsonValue, *, where: str) -> Ruling | None:
        """One decoded record as a ruling, None with a warning when it is not one."""
        try:
            return Ruling.model_validate(record)
        except ValueError:
            return Stream.skipped(f"{where} is not a ruling, skipping it")

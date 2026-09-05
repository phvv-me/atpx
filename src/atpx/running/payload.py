import json
from collections.abc import Sequence
from hashlib import sha256
from itertools import accumulate, takewhile
from pathlib import Path
from typing import ClassVar

from pydantic import JsonValue

_LIMIT = 16_000


class Capture:
    """A claim's captured output, as a certificate is allowed to carry it.

    Output that fits is carried whole. Output that does not is written whole to
    `evidence/outputs/<digest>.txt` beside the ledger it belongs to, and the
    certificate keeps whole lines from each end around a marker naming that file.
    So a stored output is either the entire text or an explicit pointer to it,
    never a JSON document cut through the middle: a reader parsing `result.output`
    can trust that what it holds ends where a line ended, and the evidence the
    certificate stopped carrying was moved rather than lost.
    """

    HOME: ClassVar[str] = "evidence/outputs"
    LIMIT: ClassVar[int] = _LIMIT

    def __init__(self, directory: Path) -> None:
        """directory: the blueprint directory oversized output is externalized under."""
        self.directory = directory

    def payload(self, output: str) -> JsonValue:
        """The structured result of a claim run, the last JSON value printed.

        Lines are scanned from the end; a line holding several concatenated JSON
        values (interleaved writers) yields its last complete value, and indented
        JSON still counts. Falls back to the captured raw output when the script
        printed no JSON at all.

        output: the combined stdout and stderr of the claim command.
        """
        text = output.strip()
        for line in reversed(text.splitlines()):
            candidate = line.strip()
            if candidate.startswith(("{", "[")) and (values := self.__decoded(candidate)):
                return values[-1]
        return dict(self.recorded(text))

    def recorded(self, text: str) -> dict[str, JsonValue]:
        """The `output` field a certificate carries, plus `elided` once the text moved out.

        The `elided` record names the character count, the digest of the whole text
        and the path it was written to, so an oversized output is externalized
        explicitly rather than silently shortened.

        text: the already stripped raw output.
        """
        if len(text) <= self.LIMIT:
            return {"output": text}
        digest = sha256(text.encode()).hexdigest()
        where = f"{self.HOME}/{digest}.txt"
        path = self.directory / where
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return {
            "output": clipped(text, limit=self.LIMIT, marker=f"whole output at {where}"),
            "elided": {"characters": len(text), "digest": f"sha256:{digest}", "path": where},
        }

    @staticmethod
    def __decoded(line: str) -> list[JsonValue]:
        """Every complete JSON value concatenated on one line, in order of appearance.

        line: one stripped output line starting with `{` or `[`.
        """
        decoder = json.JSONDecoder()
        values: list[JsonValue] = []
        position = 0
        while position < len(line):
            try:
                value, position = decoder.raw_decode(line, position)
            except json.JSONDecodeError:
                break
            values.append(value)
            while position < len(line) and line[position] in " \t":
                position += 1
        return values


def clipped(text: str, limit: int = _LIMIT, marker: str = "") -> str:
    """The whole text when it fits, else whole lines from each end around an elision marker.

    A probe's opening cases carry as much evidence as its closing summary, so a
    bounded output keeps the head and the tail rather than the tail alone. The cut
    lands only between lines: a line is kept entire or dropped entire, so a stored
    output never ends mid-token and a single oversized line collapses to the marker
    alone rather than to a corrupted middle.

    text: raw output to bound.
    limit: maximum kept characters, split evenly across head and tail.
    marker: what else the elision marker says, where the whole text can be read.
    """
    if len(text) <= limit:
        return text
    lines = text.splitlines()
    half = limit // 2
    head = _fitting(lines, half)
    tail = _fitting(lines[len(head) :][::-1], half)[::-1]
    missing = len(text) - len("\n".join(head)) - len("\n".join(tail))
    note = f"{missing} characters elided" + (f", {marker}" if marker else "")
    return "\n".join([*head, f"... [{note}] ...", *tail])


def _fitting(lines: Sequence[str], budget: int) -> list[str]:
    """The longest prefix of `lines` whose rejoined text stays inside `budget` characters.

    lines: the output lines, in the order they should be consumed.
    budget: the character allowance, the newlines between kept lines counted.
    """
    widths = accumulate(len(line) + 1 for line in lines)
    within = takewhile(lambda pair: pair[1] - 1 <= budget, zip(lines, widths, strict=True))
    return [line for line, _ in within]

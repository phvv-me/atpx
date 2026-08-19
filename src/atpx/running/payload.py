import json

from pydantic import JsonValue


def payload(output: str) -> JsonValue:
    """The structured result of a claim run, the last JSON value printed.

    Lines are scanned from the end; a line holding several concatenated JSON
    values (interleaved writers) yields its last complete value, and indented
    JSON still counts. Falls back to the tail of the raw output when the
    script printed no JSON at all.

    output: the combined stdout and stderr of the claim command.
    """
    for line in reversed(output.strip().splitlines()):
        candidate = line.strip()
        if candidate.startswith(("{", "[")) and (values := _decoded(candidate)):
            return values[-1]
    return {"output": clipped(output.strip())}


def clipped(text: str, limit: int = 16_000) -> str:
    """The whole text when it fits, else both ends around an elision marker.

    A probe's opening cases carry as much evidence as its closing summary, so a
    certificate that must truncate keeps the head and the tail rather than the
    tail alone.

    text: raw output to bound.
    limit: maximum kept characters, split evenly across head and tail.
    """
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n... [{len(text) - limit} characters elided] ...\n{text[-half:]}"


def _decoded(line: str) -> list[JsonValue]:
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

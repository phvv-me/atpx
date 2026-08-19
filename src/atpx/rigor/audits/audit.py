import json
from collections.abc import Mapping
from typing import Protocol

from pydantic import JsonValue


class Audit(Protocol):
    """One rigor gate over a probe's full output, the seam the gated verbs run behind."""

    rigor: str
    key: str

    def violation(self, output: str) -> str: ...


def witnesses(output: str, *, key: str) -> list[dict[str, JsonValue]]:
    """Every `{key: {...}}` JSON line in a probe's output, in print order.

    output: the probe's combined stdout and stderr.
    key: the witness key, `ball_certificate` or `smt_certificate`.
    """
    parsed = [_decoded(line.strip()) for line in output.splitlines()]
    found: list[dict[str, JsonValue]] = []
    for record in parsed:
        if isinstance(record, Mapping) and isinstance(witness := record.get(key), Mapping):
            found.append(dict(witness))
    return found


def _decoded(candidate: str) -> JsonValue | None:
    """One stripped line as JSON, None when it is not a JSON object line at all."""
    if not candidate.startswith("{"):
        return None
    try:
        value: JsonValue = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return value

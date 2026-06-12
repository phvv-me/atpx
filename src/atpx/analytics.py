from collections import Counter

from pydantic import JsonValue

from .roles import Status
from .zettel import Zettel

CLOSED = frozenset({Status.SKETCHED, Status.VERIFIED})


def strategy_table(nodes: list[Zettel]) -> str:
    """Close-rates by strategy tag across every node's append-only log, a markdown table.

    A strategy closes a node when that node now sits at sketched or verified.
    v1 only counts outcomes over the `[who/strategy date]` lines, it learns nothing.

    nodes: every math node the vault tracks.
    """
    lines: Counter[str] = Counter()
    touched: dict[str, set[str]] = {}
    for node in nodes:
        for entry in node.log:
            lines[entry.tag] += 1
            touched.setdefault(entry.tag, set()).add(node.name)
    closed_names = {node.name for node in nodes if node.status in CLOSED}
    rows = []
    for tag, names in touched.items():
        closed = len(names & closed_names)
        rows.append((closed / len(names), tag, lines[tag], len(names), closed))
    rows.sort(key=lambda row: (-row[0], row[1]))
    header = "| strategy | lines | nodes | closed | close rate |\n| - | - | - | - | - |"
    body = [
        f"| {tag} | {count} | {nodes_} | {closed} | {rate:.0%} |"
        for rate, tag, count, nodes_, closed in rows
    ]
    return "\n".join([header, *body])


def lean_table(nodes: list[Zettel], notes: list[Zettel]) -> str:
    """Sketched nodes ranked for formalization, backlink count over statement length.

    A documented heuristic and nothing more: load-bearing nodes (many backlinks)
    with short statements are the cheap Lean leaves worth formalizing first.

    nodes: every math node the vault tracks.
    notes: every vault note, the backlink universe.
    """
    rows = []
    for node in nodes:
        if node.status is not Status.SKETCHED:
            continue
        backlinks = sum(1 for note in notes if note.name != node.name and node.name in note.links)
        length = len(node.text)
        rows.append((backlinks / length, backlinks, length, node.name))
    rows.sort(key=lambda row: (-row[0], row[3]))
    header = "| node | backlinks | length | score |\n| - | - | - | - |"
    body = [
        f"| [[{name}]] | {backlinks} | {length} | {score:.5f} |"
        for score, backlinks, length, name in rows
    ]
    return "\n".join([header, *body])


def integer_sequences(payload: JsonValue, minimum: int = 4) -> list[tuple[int, ...]]:
    """Integer runs inside a JSON payload, the fingerprints `connect` queries.

    A run is a list made entirely of `minimum` or more integers (bools never
    count); mixed lists are walked element by element instead, and dicts are
    walked by value.

    payload: any certificate result.
    minimum: shortest run worth fingerprinting.
    """
    found: list[tuple[int, ...]] = []
    if isinstance(payload, list):
        run = tuple(x for x in payload if isinstance(x, int) and not isinstance(x, bool))
        if len(run) == len(payload) and len(run) >= minimum:
            found.append(run)
        else:
            for item in payload:
                found.extend(integer_sequences(item, minimum))
    elif isinstance(payload, dict):
        for value in payload.values():
            found.extend(integer_sequences(value, minimum))
    return list(dict.fromkeys(found))

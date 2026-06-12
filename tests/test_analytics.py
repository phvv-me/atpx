from pathlib import Path

from pydantic import JsonValue

from atpx.analytics import integer_sequences, lean_table, strategy_table
from atpx.roles import Status
from atpx.zettel import Zettel

from .conftest import zettel_text


def note(directory: Path, name: str, status: Status, body: str, log: str | None) -> Zettel:
    path = directory / f"{name}.md"
    path.write_text(zettel_text(status, title=name, body=body, log=log))
    return Zettel(path)


def test_strategy_table_aggregates_close_rates(tmp_path: Path) -> None:
    closed = note(
        tmp_path,
        "A",
        Status.SKETCHED,
        "Body.",
        "- [prover/induction 2026-06-10] step.\n- [refuter/ties 2026-06-11] survived.",
    )
    open_node = note(tmp_path, "B", Status.OPEN, "Body.", "- [prover/induction 2026-06-10] step.")
    table = strategy_table([closed, open_node])
    lines = table.splitlines()
    assert lines[0] == "| strategy | lines | nodes | closed | close rate |"
    assert lines[2] == "| ties | 1 | 1 | 1 | 100% |"
    assert lines[3] == "| induction | 2 | 2 | 1 | 50% |"


def test_strategy_table_without_logs_is_just_the_header(tmp_path: Path) -> None:
    bare = note(tmp_path, "A", Status.OPEN, "Body.", None)
    assert strategy_table([bare]).splitlines() == [
        "| strategy | lines | nodes | closed | close rate |",
        "| - | - | - | - | - |",
    ]


def test_lean_table_ranks_backlinks_over_statement_length(tmp_path: Path) -> None:
    short = note(tmp_path, "Short", Status.SKETCHED, "Tiny.", None)
    long_ = note(tmp_path, "Long", Status.SKETCHED, "A very long statement. " * 40, None)
    ignored = note(tmp_path, "Open", Status.OPEN, "Uses [[Short]] and [[Long]].", None)
    fan = note(tmp_path, "Fan", Status.SKETCHED, "Also uses [[Short]].", None)
    nodes = [short, long_, ignored, fan]
    table = lean_table(nodes, nodes)
    lines = table.splitlines()
    assert lines[2].startswith("| [[Short]] | 2 | ")
    assert lines[3].startswith("| [[Long]] | 1 | ")
    assert "[[Open]]" not in table


def test_integer_sequences_finds_pure_runs_and_walks_structures() -> None:
    payload: JsonValue = {
        "theta": [1, 196560, 16773120, 398034000],
        "short": [1, 2],
        "nested": [[0, 1, 2, 3], "prose"],
        "mixed": [True, 1, 2, 3, 4],
        "scalar": 7,
    }
    runs = integer_sequences(payload)
    assert (1, 196560, 16773120, 398034000) in runs
    assert (0, 1, 2, 3) in runs
    assert len(runs) == 2


def test_integer_sequences_deduplicates() -> None:
    run: JsonValue = [2, 3, 5, 7]
    assert integer_sequences([run, run]) == [(2, 3, 5, 7)]

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import JsonValue

from atpx import Workspace
from atpx.briefing.judgments import Ruling, RulingLedger, Severity
from atpx.core import TornLedger
from atpx.study.doctoring import DoctorReport

from ..support import FakeRunner, node_text, planted

_PROSE = "judgments/referee-theory-2026-08-28.md"


def ruled(referee: str = "referee-theory", ruling: Severity = Severity.NONE) -> Ruling:
    """One recorded ruling in the shape a human referee and a model lane both write."""
    return Ruling(
        referee=referee,
        date="2026-08-28",
        ruling=ruling,
        claim="the locking core",
        prose=_PROSE,
        rung="3",
    )


def sketching(root: Path, *, judgments: str = "") -> Workspace:
    """A workspace holding one sketched node, optionally linking a prose judgment."""
    (root / "atpx.toml").write_text('[workspace]\nblueprints = "math"\n')
    planted(
        root / "math",
        "demo",
        text=node_text(
            "sketched",
            body="A claim with no links.",
            front={"judgments": f"[{judgments}]"} if judgments else None,
        ),
    )
    return Workspace(root, runner=FakeRunner())


def unjudged(space: Workspace) -> dict[str, JsonValue]:
    """The `unjudged_sketches` slice of a fresh doctor report over one workspace."""
    report = DoctorReport(space.nodes, root=space.root, index=space.ledger_index).compiled()
    found = report["unjudged_sketches"]
    assert isinstance(found, dict)
    return found


def test_rulings_append_and_read_back_oldest_first(tmp_path: Path) -> None:
    ledger = RulingLedger(tmp_path)
    assert ledger.read("demo") == []
    ledger.record("demo", ruled("first", Severity.GAP))
    before = ledger.path("demo").read_text()
    ledger.record("demo", ruled("second", Severity.MINOR))
    assert [entry.referee for entry in ledger.read("demo")] == ["first", "second"]
    assert ledger.path("demo").read_text().startswith(before)


def test_a_ruling_line_carries_the_referee_date_ruling_claim_and_prose(tmp_path: Path) -> None:
    RulingLedger(tmp_path).record("demo", ruled(ruling=Severity.FATAL))
    (line,) = (tmp_path / "judgments" / "demo.ndjson").read_text().splitlines()
    assert json.loads(line) == {
        "referee": "referee-theory",
        "date": "2026-08-28",
        "ruling": "FATAL",
        "claim": "the locking core",
        "prose": _PROSE,
        "rung": "3",
    }


def test_one_torn_ruling_costs_only_itself(tmp_path: Path) -> None:
    ledger = RulingLedger(tmp_path)
    ledger.record("demo", ruled("kept"))
    with ledger.path("demo").open("a") as stream:
        stream.write('{"referee": "cut\n{"referee": "shaped", "date": "x"}\n')
    with pytest.warns(TornLedger):
        assert [entry.referee for entry in ledger.read("demo")] == ["kept"]


def test_a_recorded_ruling_gives_a_sketch_its_standing(tmp_path: Path) -> None:
    space = sketching(tmp_path)
    assert unjudged(space) == {"demo": ["no judgment linked in the frontmatter"]}
    RulingLedger(space.nodes.directory("demo")).record("demo", ruled())
    assert unjudged(space) == {}


def test_a_sketch_without_rulings_still_falls_back_to_its_prose_pointer(tmp_path: Path) -> None:
    """The record as it looked before rulings were data keeps reading exactly as it did."""
    space = sketching(tmp_path, judgments="ruling.md")
    assert unjudged(space) == {"demo": ["judgment ruling.md does not exist"]}
    prose = space.nodes.directory("demo") / "ruling.md"
    prose.write_text("A review naming no ladder position.\n")
    assert unjudged(space) == {"demo": ["judgment ruling.md names no attacking rung"]}
    prose.write_text("Strongest attacking rung 2.\n")
    assert unjudged(space) == {}


def test_the_rule_verb_records_the_line_it_returns(tmp_path: Path) -> None:
    space = sketching(tmp_path)
    line = space.rule("demo", "glm-5.2", Severity.MINOR, claim="Claim C", rung="4")
    recorded = RulingLedger(space.nodes.directory("demo")).read("demo")
    assert [entry.model_dump_json() for entry in recorded] == [line]
    assert recorded[0].ruling is Severity.MINOR and recorded[0].claim == "Claim C"


@given(
    rulings=st.lists(st.sampled_from(list(Severity)), min_size=1, max_size=6),
    referees=st.lists(st.from_regex(r"[a-z]{1,8}", fullmatch=True), min_size=1, max_size=6),
)
def test_every_ruling_survives_its_own_line_whatever_the_verdict(
    rulings: list[Severity], referees: list[str], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """A FATAL and a NONE land in one file under one shape, whoever wrote them."""
    ledger = RulingLedger(tmp_path_factory.mktemp("rulings"))
    written = [ruled(referee, ruling) for referee, ruling in zip(referees, rulings, strict=False)]
    for entry in written:
        ledger.record("demo", entry)
    assert ledger.read("demo") == written

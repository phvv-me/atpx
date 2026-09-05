from pathlib import Path

import pytest

from atpx import NodeStore, Status, Workspace

from ..support import FakeRunner, node_text, planted

_MATH = "research/math"


def test_the_ladder_reads_open_then_proposed_then_registered_then_in_progress() -> None:
    """Declaration order IS ladder order, and the registration regime sits inside it."""
    ladder = list(Status)
    assert ladder[:4] == [Status.OPEN, Status.PROPOSED, Status.REGISTERED, Status.IN_PROGRESS]


@pytest.mark.parametrize("status", [Status.PROPOSED, Status.REGISTERED])
def test_a_registration_settles_nothing(status: Status) -> None:
    """A promise about a run that has not happened is not a finding."""
    assert not status.is_settled


@pytest.mark.parametrize("word", ["proposed", "registered"])
def test_a_registration_word_is_a_status_and_not_an_invalid_one(root: Path, word: str) -> None:
    directory = root / _MATH / "demo"
    (directory / "node.md").write_text(node_text("open", title="Demo").replace("open", word))
    store = NodeStore(root / _MATH)
    assert store.find("demo").status is Status(word)
    assert "invalid" not in store.statuses()
    assert store.statuses()[word] == ["demo"]


def test_a_registered_node_stays_on_the_frontier(root: Path) -> None:
    """It has a spec and no run, so it is exactly what is ready to be worked next."""
    directory = root / _MATH / "demo"
    (directory / "node.md").write_text(
        node_text("open", title="Demo", body="A claim using [[dep]].").replace(
            "status: open", "status: registered"
        )
    )
    frontier = NodeStore(root / _MATH).frontier()
    assert [row["node"] for row in frontier] == ["demo"]


def test_a_registered_node_is_owed_no_results_row(root: Path) -> None:
    spec = node_text("open", title="Spec").replace("open", "registered")
    planted(root / _MATH, "spec", text=spec)
    results = root / _MATH / "RESULTS.md"
    results.write_text("# Results\n\n| a settled dep | [[dep]] | sketched |\n")
    certificate = Workspace(root, runner=FakeRunner()).doctor()
    report = certificate.result
    assert isinstance(report, dict)
    workspaces = report["workspaces"]
    assert isinstance(workspaces, dict)
    here = workspaces["."]
    assert isinstance(here, dict)
    assert here["unreported_results"] == []
    assert here["invalid_statuses"] == {}


def test_a_registration_word_cannot_be_declared_a_settled_word(tmp_path: Path) -> None:
    """A vocabulary states what a program settles ON, and a registration settles nothing."""
    (tmp_path / "atpx.toml").write_text(
        '[workspace]\nblueprints = "math"\n\n[vocabulary.registered]\nletter = "R"\n'
    )
    (tmp_path / "math").mkdir()
    with pytest.raises(ValueError, match="registered"):
        _ = Workspace(tmp_path, runner=FakeRunner()).vocabulary

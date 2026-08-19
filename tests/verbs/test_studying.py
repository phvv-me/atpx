from pathlib import Path

import pytest

from atpx import Status, Workspace

from ..support import node_text

_LEGACY_NOTE = """---
status: open
date: 2026-06-10
blueprint: research/math/fresh/
---

# Fresh Claim

A statement.
"""


def test_status_groups_by_ladder_with_an_invalid_bucket(space: Workspace, root: Path) -> None:
    odd = root / "research" / "math" / "odd"
    odd.mkdir()
    (odd / "node.md").write_text(
        node_text("open", title="Odd").replace("status: open", "status: theorem-retracted")
    )
    groups = space.status()
    assert "demo" in groups["open"] and "dep" in groups["sketched"]
    assert groups["invalid"] == ["odd (theorem-retracted)"]


def test_graph_lists_the_frontier(space: Workspace) -> None:
    (ready,) = [entry for entry in space.graph() if entry["node"] == "demo"]
    assert ready["deps"] == {"dep": "sketched"}


def test_log_appends_a_journal_line(space: Workspace) -> None:
    line = space.log("demo", "refuter", "numeric", "no counterexample up to 1e6.")
    assert line.startswith("- [refuter/numeric ")
    assert line in (space.blueprints / "demo" / "node.md").read_text()


def test_log_refuses_an_entry_that_would_not_round_trip(space: Workspace) -> None:
    with pytest.raises(ValueError, match="pattern"):
        space.log("demo", "the refuter", "numeric", "spaces break the who field")
    with pytest.raises(ValueError, match="one line"):
        space.log("demo", "refuter", "numeric", "line one\nline two")


def test_adopt_copies_a_note_and_strips_its_blueprint_line(space: Workspace) -> None:
    legacy = space.root / "notes" / "Fresh Claim.md"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(_LEGACY_NOTE)
    reported = space.adopt("fresh", source=str(legacy))
    assert reported == "research/math/fresh/node.md"
    adopted = space.nodes.find("fresh")
    assert adopted.status is Status.OPEN and legacy.exists()
    assert "blueprint:" not in adopted.text and "A statement." in adopted.text


def test_adopt_names_a_missing_source(space: Workspace) -> None:
    with pytest.raises(FileNotFoundError, match="--source"):
        space.adopt("ghost", source="nowhere/ghost.md")


def test_index_regenerates_and_writes(space: Workspace) -> None:
    text = space.index(write=True)
    assert "- [[dep]], a settled dep." in text
    assert text == space.results_index.path.read_text()


def test_index_without_write_leaves_the_file_alone(space: Workspace) -> None:
    before = space.results_index.path.read_text()
    text = space.index()
    assert "- [[dep]], a settled dep." in text
    assert space.results_index.path.read_text() == before

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


def test_index_writes_the_table_and_the_graph_beside_it(space: Workspace) -> None:
    text = space.index()
    assert "| [[dep]] | sketched | a settled dep |" in text
    assert text == space.ledger_index.path.read_text()
    assert space.ledger_index.graph_path == space.blueprints / "INDEX.json"
    assert '"slug": "dep"' in space.ledger_index.graph_path.read_text()


def test_index_moves_the_hand_written_body_under_the_manual_section(space: Workspace) -> None:
    text = space.index()
    manual = text.partition(space.ledger_index.MANUAL)[2]
    assert "Preamble prose." in manual and "Footer prose." in manual
    assert space.index() == text


def test_note_appends_a_dated_bullet_to_the_evidence_section(space: Workspace) -> None:
    line = space.note("demo", "n1 run 1 exit 0 PASS", tag="run")
    assert line.startswith("- [run ") and line.endswith("] n1 run 1 exit 0 PASS")
    text = (space.blueprints / "demo" / "node.md").read_text()
    evidence = text.partition("## Evidence")[2].partition("## Log")[0]
    assert line in evidence


def test_note_never_touches_anything_above_the_evidence_section(space: Workspace) -> None:
    node = space.blueprints / "demo" / "node.md"
    above_before = node.read_text().partition("## Evidence")[0]
    space.note("demo", "first")
    space.note("demo", "second")
    above, _, below = node.read_text().partition("## Evidence")
    assert above == above_before
    assert below.index("] first") < below.index("] second")


def test_note_refuses_a_node_without_an_evidence_section(space: Workspace) -> None:
    node = space.blueprints / "dep" / "node.md"
    node.write_text(node.read_text().replace("## Evidence\n\n", ""))
    with pytest.raises(ValueError, match="no '## Evidence' section"):
        space.note("dep", "nowhere to land")


def test_note_refuses_a_bullet_that_would_not_round_trip(space: Workspace) -> None:
    with pytest.raises(ValueError, match="one line"):
        space.note("demo", "line one\nline two")
    with pytest.raises(ValueError, match="tag"):
        space.note("demo", "fine", tag="not a tag")


def test_design_scaffolds_a_pre_registration_and_allocates_a_seed(space: Workspace) -> None:
    filed = space.design("demo")
    path = space.root / filed
    assert path.parent == space.blueprints / "demo" and path.name.startswith("design-")
    text = path.read_text()
    headings = {line for line in text.splitlines() if line.startswith("## ")}
    fields = {"Hypothesis", "Observable", "Conditions", "Decision rule", "Seed base"}
    assert {f"## {field}" for field in fields | {"Cost estimate", "Exploratory"}} <= headings
    (seed,) = space.nodes.find("demo").front.seeds
    assert f"## Seed base\n\n{seed}," in text

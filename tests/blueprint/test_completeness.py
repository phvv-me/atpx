from pathlib import Path

from atpx import Workspace
from atpx.briefing import JudgmentLedger

from ..support import FakeRunner, node_text, planted, result_of

_MATH = "research/math"


def reported(space: Workspace) -> dict[str, dict[str, dict[str, object]]]:
    """This workspace's own report out of one `doctor` run."""
    return result_of(space.doctor())["workspaces"]["."]


def test_doctor_flags_a_node_below_the_completeness_contract(root: Path) -> None:
    """A claim without a statement of record or a refutation condition is not ready to run."""
    planted(
        root / _MATH,
        "hollow",
        text=node_text("open", title="Hollow", body="<!-- todo -->", refutation=None),
    )
    report = reported(Workspace(root, runner=FakeRunner()))
    assert report["unstated_nodes"] == ["hollow"]
    assert report["unconditioned_nodes"] == ["hollow"]


def test_doctor_exempts_a_probe_pool_from_the_claim_contract(root: Path) -> None:
    """A probe pool carries no claim, no status, and no refutation condition by design."""
    planted(
        root / _MATH,
        "pool",
        text=node_text(
            None,
            title="pool",
            body="A shared probe library.",
            refutation=None,
            front={"kind": "probe-pool"},
        ),
    )
    report = reported(Workspace(root, runner=FakeRunner()))
    assert "pool" not in report["invalid_statuses"]
    assert report["unstated_nodes"] == [] and report["unconditioned_nodes"] == []


def test_doctor_reports_frontmatter_that_does_not_parse(root: Path) -> None:
    planted(root / _MATH, "bare", text="# Bare\n\nRefutation condition. Prose only.\n")
    seeded = root / _MATH / "demo" / "node.md"
    seeded.write_text(seeded.read_text().replace("---\nstatus:", "---\nseeds: [1, soup]\nstatus:"))
    report = reported(Workspace(root, runner=FakeRunner()))
    assert report["frontmatter_problems"] == {
        "bare": ["no frontmatter block"],
        "demo": ["seeds entry 'soup' is not an integer"],
    }


def test_doctor_demands_a_linked_judgment_on_every_sketch(root: Path) -> None:
    node = root / _MATH / "dep" / "node.md"
    node.write_text(node.read_text().replace("judgments: [judgments/draft.md]\n", ""))
    report = reported(Workspace(root, runner=FakeRunner()))
    assert report["unjudged_sketches"] == {"dep": ["no judgment linked in the frontmatter"]}


def test_doctor_names_what_is_wrong_with_each_linked_judgment(root: Path) -> None:
    dep = root / _MATH / "dep"
    (dep / "judgments" / "draft.md").write_text("Survived, no ladder details recorded.\n")
    node = dep / "node.md"
    node.write_text(
        node.read_text().replace(
            "judgments: [judgments/draft.md]",
            "judgments: [judgments/draft.md, judgments/ghost.md]",
        )
    )
    report = reported(Workspace(root, runner=FakeRunner()))
    assert report["unjudged_sketches"] == {
        "dep": [
            "judgment judgments/draft.md names no attacking rung",
            "judgment judgments/ghost.md does not exist",
        ]
    }


def test_doctor_flags_a_statement_that_drifted_from_its_snapshot(root: Path) -> None:
    """Appending evidence below the statement is free; editing the statement is drift."""
    space = Workspace(root, runner=FakeRunner())
    dep = space.nodes.find("dep")
    JudgmentLedger(dep.directory).record(dep)
    space.note("dep", "a fresh certificate landed", tag="run")
    assert reported(space)["drifted_statements"] == {}
    node = dep.directory / "node.md"
    node.write_text(node.read_text().replace("Settled.", "Settled, and then some."))
    assert reported(space)["drifted_statements"] == {
        "dep": "statement differs from its judgment snapshot"
    }


def test_doctor_flags_a_stale_index_and_index_refreshes_it(root: Path) -> None:
    space = Workspace(root, runner=FakeRunner())
    both = ["research/math/INDEX.md", "research/math/INDEX.json"]
    assert reported(space)["stale_index"] == both
    space.index()
    assert reported(space)["stale_index"] == []
    space.settle("demo", "abandoned", "shelved")
    assert reported(space)["stale_index"] == both

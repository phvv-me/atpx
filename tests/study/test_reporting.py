from pathlib import Path

import pytest

from atpx import Workspace

from ..support import FakeRunner, node_text, planted, result_of

_MATH = "research/math"


def reported(root: Path) -> dict[str, object]:
    """This workspace's own slice of a fresh doctor report."""
    found = result_of(Workspace(root, runner=FakeRunner()).doctor())["workspaces"]["."]
    assert isinstance(found, dict)
    return found


@pytest.fixture
def results(root: Path) -> Path:
    """The hand-authored results table beside the fixture workspace's index."""
    return root / _MATH / "RESULTS.md"


def test_a_workspace_with_no_results_table_is_owed_no_rows(root: Path) -> None:
    """Most workspaces keep no results table, and none of them is told to start one."""
    assert reported(root)["unreported_results"] == []


def test_a_settled_node_with_no_row_fails_the_gate(root: Path, results: Path) -> None:
    results.write_text("# Results\n\nNothing settled yet.\n")
    certificate = Workspace(root, runner=FakeRunner()).doctor()
    found = result_of(certificate)["workspaces"]["."]
    assert isinstance(found, dict)
    assert found["unreported_results"] == ["dep"]
    assert ".: unreported_results" in result_of(certificate)["breakages"]


def test_a_row_citing_the_node_clears_it(root: Path, results: Path) -> None:
    """One row settles the only settled node; `demo` is open and `blocked` in progress,
    so neither of them has a finding to report yet either.
    """
    results.write_text("# Results\n\n| a settled dep | [[dep]] | sketched |\n")
    assert reported(root)["unreported_results"] == []


def test_a_row_citing_a_superseded_stub_is_pointed_at_the_node_of_record(
    root: Path, results: Path
) -> None:
    planted(
        root / _MATH,
        "moved-claim",
        text=node_text(
            "sketched",
            title="Moved",
            front={"superseded_by": "math/moved_claim", "judgments": "[judgments/draft.md]"},
        ),
    )
    planted(root / _MATH, "moved_claim", text=node_text("validated", title="Moved claim"))
    results.write_text("# Results\n\n| finding | [[moved-claim]] | [[dep]] |\n")
    found = reported(root)
    assert found["misdirected_citations"] == {
        "moved-claim": "cite [[moved_claim]], the node of record math/moved_claim this stub "
        "points at"
    }
    assert found["unreported_results"] == ["moved_claim"]

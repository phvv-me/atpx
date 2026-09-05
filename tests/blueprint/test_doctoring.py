from pathlib import Path

import pytest
from plumbum import local
from pydantic import JsonValue

from atpx import EvidenceStore, Workspace
from atpx.study.doctoring import DoctorReport

from ..support import FakeRunner, node_text, planted, result_of, stamped

_MATH = "research/math"
_LENS = "research/thoughtlens"


def reported(space: Workspace) -> dict[str, dict[str, dict[str, object]]]:
    """Each workspace's own report out of one `doctor` run, keyed by path."""
    return result_of(space.doctor())["workspaces"]


def _closed_status_without_a_manifest(blueprints: Path) -> None:
    odd = blueprints / "odd"
    odd.mkdir()
    (odd / "node.md").write_text(
        node_text("open", title="Odd", body="Leans on [[ghost]].").replace(
            "status: open", "status: closed"
        )
    )


def _stray_evidence_file(blueprints: Path) -> None:
    stray_home = blueprints / "demo" / "evidence"
    stray_home.mkdir(parents=True, exist_ok=True)
    (stray_home / "routing_data.json").write_text('{"tokens": 684}')


def _nodeless_blueprint(blueprints: Path) -> None:
    nodeless = blueprints / "nodeless"
    nodeless.mkdir()
    (nodeless / "atpx.toml").write_text("[claims]\n")


@pytest.fixture
def messy_root(root: Path) -> Path:
    """The fixture workspace with one of every ailment `doctor` reports."""
    blueprints = root / _MATH
    _closed_status_without_a_manifest(blueprints)
    _stray_evidence_file(blueprints)
    (blueprints / "orphan").mkdir()
    _nodeless_blueprint(blueprints)
    (blueprints / "notes.txt").write_text("not a blueprint\n")
    return root


@pytest.fixture
def nested_root(root: Path) -> Path:
    """The fixture workspace with a second, independent workspace inside it."""
    inner = root / _LENS
    (inner / "math").mkdir(parents=True)
    (inner / "atpx.toml").write_text('[workspace]\nblueprints = "math"\n')
    planted(inner / "math", "lensed", text=node_text("sketched", title="Lensed"))
    return root


def test_doctor_reports_instead_of_crashing(messy_root: Path) -> None:
    space = Workspace(messy_root, runner=FakeRunner())
    report = reported(space)["."]
    assert report["invalid_statuses"] == {"odd": "closed"}
    assert report["stray_evidence"] == {"demo": ["research/math/demo/evidence/routing_data.json"]}
    assert report["unmanifested_blueprints"] == ["odd", "orphan"]
    assert "notes.txt" not in report["unmanifested_blueprints"]
    assert report["nodeless_blueprints"] == ["nodeless"]
    assert report["dangling_links"] == {"odd": ["ghost"]}
    assert space.status()["invalid"] == ["odd (closed)"]


def test_a_doctored_workspace_still_runs_checks(messy_root: Path) -> None:
    space = Workspace(messy_root, runner=FakeRunner())
    assert space.sync.check("demo", "ok").ok


def test_doctor_fails_the_gate_only_on_findings_that_contradict_the_workspace(
    messy_root: Path,
) -> None:
    certificate = Workspace(messy_root, runner=FakeRunner()).doctor()
    assert not certificate.ok
    assert result_of(certificate)["breakages"] == [
        ".: invalid_statuses",
        ".: dangling_links",
        ".: unevidenced_claims",
        ".: stale_index",
    ]


def test_doctor_tolerates_untidiness_without_failing(root: Path) -> None:
    """Stray data files and manifest-less directories report, and never gate."""
    _stray_evidence_file(root / _MATH)
    (root / _MATH / "orphan").mkdir()
    EvidenceStore(root / _MATH / "demo").append(stamped("demo/ok"))
    EvidenceStore(root / _MATH / "demo").append(stamped("demo/gpu"))
    space = Workspace(root, runner=FakeRunner())
    space.index()
    certificate = space.doctor()
    report = result_of(certificate)["workspaces"]["."]
    assert certificate.ok and report["stray_evidence"] and report["unmanifested_blueprints"]
    assert report["undesigned_evidence"] == ["demo"]


def test_doctor_flags_a_claim_whose_newest_evidence_failed(root: Path) -> None:
    directory = root / _MATH / "demo"
    EvidenceStore(directory).append(stamped("demo/ok").model_copy(update={"exit_status": 2}))
    EvidenceStore(directory).append(stamped("demo/gpu"))
    report = reported(Workspace(root, runner=FakeRunner()))["."]
    assert report["failing_claims"] == {"demo": ["ok"]}
    assert report["unevidenced_claims"] == {}


def test_doctor_flags_a_claim_no_host_ever_certified(root: Path) -> None:
    EvidenceStore(root / _MATH / "demo").append(stamped("demo/ok"))
    report = reported(Workspace(root, runner=FakeRunner()))["."]
    assert report["unevidenced_claims"] == {"demo": ["gpu"]}


def test_doctor_reads_every_nested_workspace_from_the_top(nested_root: Path) -> None:
    """One invocation answers for the whole tree, so no caller has to pin a root per project."""
    found = reported(Workspace(nested_root, runner=FakeRunner()))
    assert set(found) == {".", _LENS}
    assert found[_LENS]["invalid_statuses"] == {}


def test_doctor_fails_when_only_a_nested_workspace_is_broken(nested_root: Path) -> None:
    node = nested_root / _LENS / "math" / "lensed" / "node.md"
    node.write_text(node.read_text().replace("status: sketched", "status: immaculate"))
    certificate = Workspace(nested_root, runner=FakeRunner()).doctor()
    assert not certificate.ok
    assert f"{_LENS}: invalid_statuses" in result_of(certificate)["breakages"]


def test_breakages_never_name_a_tolerated_finding() -> None:
    tolerated: dict[str, JsonValue] = {
        "stray_evidence": {"demo": ["x.json"]},
        "unmanifested_blueprints": ["orphan"],
    }
    assert DoctorReport.breakages(tolerated) == []


def committed(root: Path) -> str:
    """Track everything under `root` in a fresh repository, returning its short revision."""
    git = local["git"]["-C", str(root)]
    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    git("add", ".")
    git("commit", "-qm", "first")
    return str(git("rev-parse", "--short", "HEAD")).strip()


def test_doctor_flags_evidence_older_than_the_statement_it_supports(root: Path) -> None:
    """Editing a node without re-running its checks leaves evidence certifying the old text."""
    stamped_at = committed(root)
    directory = root / _MATH / "demo"
    node = directory / "node.md"
    node.write_text(node.read_text() + "\nA sharper statement.\n")
    local["git"]["-C", str(root)]("commit", "-qam", "revised")
    for claim in ("ok", "gpu"):
        EvidenceStore(directory).append(
            stamped(f"demo/{claim}").model_copy(update={"git_rev": stamped_at})
        )
    report = reported(Workspace(root, runner=FakeRunner()))["."]
    assert report["stale_claims"] == {"demo": ["gpu", "ok"]}


def test_doctor_fails_when_a_node_and_its_result_note_disagree(root: Path) -> None:
    """The exact drift that hid a settled campaign: the note settled it, the node never moved."""
    directory = root / _MATH / "demo"
    (directory / "node.md").write_text(node_text("in_progress", title="Demo"))
    (directory / "result.md").write_text("# Demo result\n\nStatus: **validated** on 2026-09-04.\n")
    certificate = Workspace(root, runner=FakeRunner()).doctor()
    report = result_of(certificate)["workspaces"]["."]
    assert report["contradicted_results"] == {
        "demo": "node says in_progress, result.md says validated"
    }
    assert ".: contradicted_results" in result_of(certificate)["breakages"]


def test_doctor_is_quiet_when_a_node_and_its_result_note_agree(root: Path) -> None:
    directory = root / _MATH / "demo"
    (directory / "node.md").write_text(node_text("validated", title="Demo"))
    (directory / "result.md").write_text("Status: validated\n")
    assert reported(Workspace(root, runner=FakeRunner()))["."]["contradicted_results"] == {}


def test_doctor_reads_a_second_node_document_in_the_same_directory(root: Path) -> None:
    """Two registrations in one campaign directory are two nodes carrying two states."""
    successor = root / _MATH / "demo" / "v2-node.md"
    successor.write_text(node_text("open", title="Demo v2").replace("open", "immaculate"))
    report = reported(Workspace(root, runner=FakeRunner()))["."]
    assert report["invalid_statuses"] == {"demo/v2": "immaculate"}


def test_doctor_flags_two_names_for_one_claim_with_nothing_joining_them(root: Path) -> None:
    planted(root / _MATH, "x-structure", text=node_text("open", title="X structure"))
    planted(root / _MATH, "x_structure", text=node_text("open", title="X structure"))
    report = reported(Workspace(root, runner=FakeRunner()))["."]
    assert report["unjoined_twins"] == {
        "x-structure, x_structure": "two names for one separator, with no relation joining "
        "them; point one at the other or rename it"
    }


def test_a_relation_joins_a_pair_of_names_however_it_spells_the_pointer(root: Path) -> None:
    """A migration between roots writes the qualified pointer, and that joins the pair too."""
    planted(
        root / _MATH,
        "x-structure",
        text=node_text("open", title="X structure", front={"superseded_by": "math/x_structure"}),
    )
    planted(root / _MATH, "x_structure", text=node_text("open", title="X structure"))
    assert reported(Workspace(root, runner=FakeRunner()))["."]["unjoined_twins"] == {}

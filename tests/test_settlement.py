import pytest

from atpx.evidence import EvidenceStore
from atpx.roles import Status
from atpx.settlement import Gate, Petition, SettleError, Settlement
from atpx.workspace import Workspace
from atpx.zettel import LOG_LINE

from .conftest import FakeRunner, stamped


def test_free_statuses_have_no_gate_and_need_no_evidence(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, runner = ws
    assert Gate.of(Status.OPEN) is None
    space.settle("Demo Node", "in_progress", "picking this up.")
    assert space.vault.find("Demo Node").status is Status.IN_PROGRESS
    space.settle("Demo Node", "known", "already in Conway and Sloane.")
    assert space.vault.find("Demo Node").status is Status.KNOWN


def test_sketched_demands_a_judgment_file(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    with pytest.raises(SettleError, match="judgment"):
        space.settle("Demo Node", "sketched")
    ruling = space.root / "research" / "math" / "demo" / "ruling.md"
    ruling.write_text("NONE. The argument holds.\n")
    line = space.settle("Demo Node", "sketched", "refuter survived.", judgment=str(ruling))
    assert line.endswith(f"refuter survived. judgment {ruling}")
    assert space.vault.find("Demo Node").status is Status.SKETCHED
    assert (space.blueprints / "demo" / "judgments" / "Demo Node.json").exists()


def test_sketched_accepts_a_cwd_relative_ruling(
    ws: tuple[Workspace, FakeRunner],
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    space, runner = ws
    elsewhere = tmp_path_factory.mktemp("rulings")
    (elsewhere / "ruling.md").write_text("NONE.\n")
    monkeypatch.chdir(elsewhere)
    space.settle("Demo Node", "sketched", judgment="ruling.md")
    assert space.vault.find("Demo Node").status is Status.SKETCHED


def test_sketched_without_a_blueprint_skips_the_snapshot(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, runner = ws
    ruling = space.root / "ruling.md"
    ruling.write_text("NONE.\n")
    space.settle("Blocked", "sketched", judgment=str(ruling))
    assert space.vault.find("Blocked").status is Status.SKETCHED


def test_refuted_demands_a_persisted_counterexample(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    with pytest.raises(SettleError, match="certificate"):
        space.settle("Demo Node", "refuted", counterexample="demo/kill")
    EvidenceStore(space.blueprints / "demo").append(stamped("demo/kill", exit_status=1))
    line = space.settle("Demo Node", "refuted", "tie broken wrong.", counterexample="kill")
    assert line.endswith("counterexample demo/kill")
    assert space.vault.find("Demo Node").status is Status.REFUTED


def test_refuted_matches_an_exact_claim_id(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    EvidenceStore(space.blueprints / "demo").append(stamped("demo/kill", exit_status=1))
    space.settle("Demo Node", "refuted", counterexample="demo/kill")
    assert space.vault.find("Demo Node").status is Status.REFUTED


def test_certified_demands_a_reference_and_a_blueprint(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    with pytest.raises(SettleError, match="reference"):
        space.settle("Demo Node", "refuted")
    with pytest.raises(SettleError, match="blueprint field"):
        space.settle("Blocked", "refuted", counterexample="demo/kill")


def test_certified_walks_past_a_ledger_without_the_match(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, runner = ws
    directory = space.blueprints / "demo"
    foreign = stamped("demo/other").model_copy(update={"hostname": "aaa-first"})
    EvidenceStore(directory, hostname="aaa-first").append(foreign)
    EvidenceStore(directory).append(stamped("demo/kill", exit_status=1))
    space.settle("Demo Node", "refuted", "dead.", counterexample="kill")
    assert space.vault.find("Demo Node").status is Status.REFUTED


def test_verified_demands_a_clean_lean_certificate(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    store = EvidenceStore(space.blueprints / "demo")
    dirty = stamped("demo/lean").model_copy(update={"result": {"sorries": 2}})
    store.append(dirty)
    with pytest.raises(SettleError, match="clean Lean build"):
        space.settle("Demo Node", "verified", lean="demo/lean")
    clean = stamped("demo/lean2").model_copy(update={"result": {"sorries": 0, "flagged": []}})
    store.append(clean)
    space.settle("Demo Node", "verified", "statement back-translates.", lean="demo/lean2")
    assert space.vault.find("Demo Node").status is Status.VERIFIED


def test_verified_refuses_a_flagged_lean_certificate(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    tainted = stamped("demo/lean3").model_copy(
        update={"result": {"sorries": 0, "flagged": ["native_decide"]}}
    )
    EvidenceStore(space.blueprints / "demo").append(tainted)
    with pytest.raises(SettleError, match="risky axioms"):
        space.settle("Demo Node", "verified", lean="demo/lean3")
    assert space.vault.find("Demo Node").status is not Status.VERIFIED


def test_verified_refuses_a_failed_build_and_a_non_audit_certificate(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, runner = ws
    store = EvidenceStore(space.blueprints / "demo")
    failed = stamped("demo/lean4", exit_status=1).model_copy(
        update={"result": {"sorries": 0, "flagged": []}}
    )
    store.append(failed)
    with pytest.raises(SettleError, match="clean Lean build"):
        space.settle("Demo Node", "verified", lean="demo/lean4")
    shapeless = stamped("demo/lean5").model_copy(update={"result": "just prose"})
    store.append(shapeless)
    with pytest.raises(SettleError, match="clean Lean build"):
        space.settle("Demo Node", "verified", lean="demo/lean5")


def test_settle_rejects_unknown_status_values(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    with pytest.raises(ValueError):
        space.settle("Demo Node", "immaculate")


def test_move_journals_a_line_the_parser_reads_back(ws: tuple[Workspace, FakeRunner]) -> None:
    """A bare settle (no message) must still land as a parseable journal entry.

    The old formatter rstripped the line, which the `- [who/tag date] ` parser
    then skipped, so message-less settles vanished from `last_judgment`.
    """
    space, runner = ws
    node = space.vault.find("Demo Node")
    line = Settlement(space.root).move(node, Status.ABANDONED, Petition())
    ((who, tag, date, message),) = LOG_LINE.findall(line)
    assert (who, tag, message) == ("settle", "abandoned", "")
    assert "  " not in line

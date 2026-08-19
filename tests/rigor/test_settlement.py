import pytest

from atpx import EvidenceStore, SettleError, Status, Workspace
from atpx.settlement import (
    Gate,
    Petition,
    RefuteGate,
    Settlement,
    SketchGate,
    ValidateGate,
    VerifyGate,
)

from ..support import stamped


def test_free_statuses_have_no_gate_and_need_no_evidence(space: Workspace) -> None:
    assert Gate.of(Status.OPEN) is None
    space.settle("demo", "in_progress", "picking this up.")
    assert space.nodes.find("demo").status is Status.IN_PROGRESS
    space.settle("demo", "known", "already in Conway and Sloane.")
    assert space.nodes.find("demo").status is Status.KNOWN


def test_settle_moves_a_free_status_and_journals_it(space: Workspace) -> None:
    line = space.settle("demo", "in_progress", "picking this up.")
    assert line.startswith("- [settle/in_progress ")
    assert space.nodes.find("demo").status is Status.IN_PROGRESS


def test_every_gated_status_resolves_to_its_own_gate() -> None:
    """Pin the registry wiring `Gate.of` depends on.

    `Gate.of` discovers each concrete gate through `patos.Registry`, not by name, so a gate
    that stops being imported anywhere silently drops its transition's evidence demand instead
    of failing loudly. Naming every concrete class here through its public route pins that wiring.
    """
    assert isinstance(Gate.of(Status.SKETCHED), SketchGate)
    assert isinstance(Gate.of(Status.REFUTED), RefuteGate)
    assert isinstance(Gate.of(Status.VALIDATED), ValidateGate)
    assert isinstance(Gate.of(Status.VERIFIED), VerifyGate)


def test_sketched_demands_a_judgment_file(space: Workspace) -> None:
    with pytest.raises(SettleError, match="judgment"):
        space.settle("demo", "sketched")
    ruling = space.root / "research" / "math" / "demo" / "ruling.md"
    ruling.write_text("NONE. The argument holds.\n")
    line = space.settle("demo", "sketched", "refuter survived.", judgment=str(ruling))
    assert line.endswith(f"refuter survived. judgment {ruling}")
    assert space.nodes.find("demo").status is Status.SKETCHED
    assert (space.blueprints / "demo" / "judgments" / "demo.json").exists()


def test_sketched_accepts_a_cwd_relative_ruling(
    space: Workspace,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    elsewhere = tmp_path_factory.mktemp("rulings")
    (elsewhere / "ruling.md").write_text("NONE.\n")
    monkeypatch.chdir(elsewhere)
    space.settle("demo", "sketched", judgment="ruling.md")
    assert space.nodes.find("demo").status is Status.SKETCHED


def test_sketched_snapshots_the_judged_node_in_its_blueprint(space: Workspace) -> None:
    ruling = space.root / "ruling.md"
    ruling.write_text("NONE.\n")
    space.settle("blocked", "sketched", judgment=str(ruling))
    assert space.nodes.find("blocked").status is Status.SKETCHED
    assert (space.blueprints / "blocked" / "judgments" / "blocked.json").exists()


def test_refuted_demands_a_persisted_counterexample(space: Workspace) -> None:
    with pytest.raises(SettleError, match="certificate"):
        space.settle("demo", "refuted", counterexample="demo/kill")
    EvidenceStore(space.blueprints / "demo").append(stamped("demo/kill", exit_status=1))
    line = space.settle("demo", "refuted", "tie broken wrong.", counterexample="kill")
    assert line.endswith("counterexample demo/kill")
    assert space.nodes.find("demo").status is Status.REFUTED


def test_refuted_matches_an_exact_claim_id(space: Workspace) -> None:
    EvidenceStore(space.blueprints / "demo").append(stamped("demo/kill", exit_status=1))
    space.settle("demo", "refuted", counterexample="demo/kill")
    assert space.nodes.find("demo").status is Status.REFUTED


@pytest.mark.parametrize("rigor", ["ball", "smt", "exact"])
def test_validated_accepts_a_rigorous_certificate(space: Workspace, rigor: str) -> None:
    EvidenceStore(space.blueprints / "demo").append(
        stamped("demo/proof").model_copy(update={"rigor": rigor})
    )
    line = space.settle("demo", "validated", "enclosure holds.", certificate="proof")
    assert line.endswith("certificate demo/proof")
    assert space.nodes.find("demo").status is Status.VALIDATED


def test_validated_refuses_a_sampled_certificate(space: Workspace) -> None:
    EvidenceStore(space.blueprints / "demo").append(stamped("demo/proof"))
    with pytest.raises(SettleError, match="rigor 'sampled'"):
        space.settle("demo", "validated", certificate="proof")
    assert space.nodes.find("demo").status is not Status.VALIDATED


def test_validated_refuses_a_missing_certificate(space: Workspace) -> None:
    with pytest.raises(SettleError, match="reference"):
        space.settle("demo", "validated")
    with pytest.raises(SettleError, match="no certificate"):
        space.settle("demo", "validated", certificate="ghost")


def test_validated_refuses_a_dirty_exit(space: Workspace) -> None:
    EvidenceStore(space.blueprints / "demo").append(
        stamped("demo/proof", exit_status=1).model_copy(update={"rigor": "ball"})
    )
    with pytest.raises(SettleError, match="exited 1"):
        space.settle("demo", "validated", certificate="proof")


def test_the_demand_walks_past_a_ledger_without_the_match(space: Workspace) -> None:
    directory = space.blueprints / "demo"
    foreign = stamped("demo/other").model_copy(update={"hostname": "aaa-first"})
    EvidenceStore(directory, hostname="aaa-first").append(foreign)
    EvidenceStore(directory).append(stamped("demo/kill", exit_status=1))
    space.settle("demo", "refuted", "dead.", counterexample="kill")
    assert space.nodes.find("demo").status is Status.REFUTED


def test_verified_demands_a_clean_lean_certificate(space: Workspace) -> None:
    store = EvidenceStore(space.blueprints / "demo")
    dirty = stamped("demo/lean").model_copy(update={"result": {"sorries": 2}})
    store.append(dirty)
    with pytest.raises(SettleError, match="clean Lean build"):
        space.settle("demo", "verified", lean="demo/lean")
    clean = stamped("demo/lean2").model_copy(update={"result": {"sorries": 0, "flagged": []}})
    store.append(clean)
    space.settle("demo", "verified", "statement back-translates.", lean="demo/lean2")
    assert space.nodes.find("demo").status is Status.VERIFIED


def test_verified_refuses_a_flagged_lean_certificate(space: Workspace) -> None:
    tainted = stamped("demo/lean3").model_copy(
        update={"result": {"sorries": 0, "flagged": ["native_decide"]}}
    )
    EvidenceStore(space.blueprints / "demo").append(tainted)
    with pytest.raises(SettleError, match="risky axioms"):
        space.settle("demo", "verified", lean="demo/lean3")
    assert space.nodes.find("demo").status is not Status.VERIFIED


def test_verified_refuses_a_failed_build_and_a_non_audit_certificate(space: Workspace) -> None:
    store = EvidenceStore(space.blueprints / "demo")
    failed = stamped("demo/lean4", exit_status=1).model_copy(
        update={"result": {"sorries": 0, "flagged": []}}
    )
    store.append(failed)
    with pytest.raises(SettleError, match="clean Lean build"):
        space.settle("demo", "verified", lean="demo/lean4")
    shapeless = stamped("demo/lean5").model_copy(update={"result": "just prose"})
    store.append(shapeless)
    with pytest.raises(SettleError, match="clean Lean build"):
        space.settle("demo", "verified", lean="demo/lean5")


def test_settle_rejects_unknown_status_values(space: Workspace) -> None:
    with pytest.raises(ValueError):
        space.settle("demo", "immaculate")


def test_move_journals_a_line_the_parser_reads_back(space: Workspace) -> None:
    """A bare settle (no message) must still land as a parseable journal entry.

    The old formatter rstripped the line, which the `- [who/tag date] ` parser
    then skipped, so message-less settles vanished from `last_judgment`.
    """
    node = space.nodes.find("demo")
    line = Settlement(space.root).move(node, Status.ABANDONED, Petition())
    entry = space.nodes.find("demo").log[-1]
    assert (entry.who, entry.tag, entry.message) == ("settle", "abandoned", "")
    assert "  " not in line

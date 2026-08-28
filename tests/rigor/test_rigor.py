import json
from pathlib import Path

import pytest

from atpx import Certificate, EvidenceStore, Workspace
from atpx.rigor import hunted

from ..support import FakeRunner, evidence_entries, result_of, stamped
from .test_audits import ball_line, receipt_line, smt_line


def gated_workspace(root: Path, output: str, exit_status: int = 0) -> Workspace:
    """A workspace whose runner replays one canned probe transcript."""
    return Workspace(root, runner=FakeRunner(exit_status=exit_status, output=output))


def violation_of(certificate: Certificate) -> str:
    """The gate violation one stamped certificate recorded, empty when it passed."""
    return str(result_of(certificate)["violation"])


def test_ball_verb_stamps_ball_rigor_and_persists(root: Path) -> None:
    space = gated_workspace(root, f"{ball_line('a')}\n{ball_line('b')}\n")
    certificate = space.sync.ball("fresh", "octave", "python", "probe.py")
    assert certificate.ok and certificate.rigor == "ball"
    assert violation_of(certificate) == ""
    (entry,) = evidence_entries(space.nodes.directory("fresh"))
    assert entry["rigor"] == "ball" and entry["claim"] == "fresh/octave"


def test_ball_verb_forces_a_nonzero_exit_on_an_unverified_witness(root: Path) -> None:
    space = gated_workspace(root, ball_line("leaky", verified=False) + "\n")
    certificate = space.sync.ball("fresh", "octave", "python", "probe.py")
    assert certificate.exit_status == 1 and certificate.rigor == "sampled"
    assert "leaky" in violation_of(certificate)


def test_ball_verb_keeps_a_probe_failure_sampled(root: Path) -> None:
    space = gated_workspace(root, "boom\n", exit_status=3)
    certificate = space.sync.ball("fresh", "octave", "python", "probe.py")
    assert certificate.exit_status == 3 and certificate.rigor == "sampled"
    assert violation_of(certificate) == "exit 3"


def test_smt_verb_stamps_smt_rigor_on_unsat(root: Path) -> None:
    space = gated_workspace(root, f"encoding printed\n{smt_line()}\n")
    certificate = space.sync.smt("fresh", "forcing", "python", "probe.py")
    assert certificate.ok and certificate.rigor == "smt"
    (witness,) = result_of(certificate)["witnesses"]
    assert witness["logic"] == "QF_LRA"


def test_smt_verb_fails_the_gate_on_sat(root: Path) -> None:
    space = gated_workspace(root, f"model: rP = 1\n{smt_line('negation', result='sat')}\n")
    certificate = space.sync.smt("fresh", "forcing", "python", "probe.py")
    assert certificate.exit_status == 1 and certificate.rigor == "sampled"
    assert "model: rP = 1" in result_of(certificate)["output"]


def test_lab_verb_records_the_trial_identity_the_experiment_reported(root: Path) -> None:
    space = gated_workspace(root, f"staging\n{receipt_line('9d3c1a77b2e40f5b')}\n")
    certificate = space.sync.lab("fresh", "collapse", "python", "-m", "study")
    assert certificate.ok and certificate.rigor == "lab"
    (witness,) = result_of(certificate)["witnesses"]
    assert witness["run_id"] == "9d3c1a77b2e40f5b"
    (entry,) = evidence_entries(space.nodes.directory("fresh"))
    assert entry["rigor"] == "lab" and entry["claim"] == "fresh/collapse"


def test_lab_verb_refuses_rigor_when_a_gate_withheld_the_trial(root: Path) -> None:
    space = gated_workspace(root, receipt_line("abc", outcome="blocked", reason="GPU busy"))
    certificate = space.sync.lab("fresh", "collapse", "python", "-m", "study")
    assert certificate.exit_status == 1 and certificate.rigor == "sampled"
    assert "GPU busy" in violation_of(certificate)


def test_lab_verb_replays_the_registered_command_with_no_argv(root: Path) -> None:
    """Re-verification is the same verb again, so evidence regenerates from the manifest."""
    space = gated_workspace(root, receipt_line())
    space.sync.lab("fresh", "collapse", "python", "-m", "study")
    replayed = space.sync.lab("fresh", "collapse")
    assert replayed.ok and replayed.rigor == "lab"


def test_hunt_reads_exit_zero_as_a_found_counterexample(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    space = gated_workspace(root, "falsifying example: []\n")
    certificate = space.sync.hunt("fresh", "doubling", "python", "probe.py")
    assert certificate.ok and certificate.rigor == "sampled"
    assert "counterexample FOUND" in capsys.readouterr().out
    (entry,) = evidence_entries(space.nodes.directory("fresh"))
    assert entry["rigor"] == "sampled"


def test_hunt_reads_a_nonzero_exit_as_survival(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    space = gated_workspace(root, "no counterexample\n", exit_status=1)
    certificate = space.sync.hunt("fresh", "doubling", "python", "probe.py")
    assert not certificate.ok
    assert "survived the search (exit 1)" in capsys.readouterr().out


def test_hunted_lines_name_the_claim() -> None:
    assert "demo/ok" in hunted(stamped())
    assert "no counterexample found" in hunted(stamped(exit_status=1))


def test_rigor_round_trips_through_the_ledger(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    store.append(stamped().model_copy(update={"rigor": "ball"}))
    (entry,) = store.read()
    assert entry.rigor == "ball"


def test_a_ledger_predating_rigor_reads_as_sampled(tmp_path: Path) -> None:
    """The pre-migration array format, read exactly as it was recorded."""
    store = EvidenceStore(tmp_path)
    record = stamped().model_dump()
    del record["rigor"]
    store.array.parent.mkdir(parents=True)
    store.array.write_text(json.dumps([record]))
    (entry,) = store.read()
    assert entry.rigor == "sampled"

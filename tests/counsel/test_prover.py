import json
from pathlib import Path

import pytest

from atpx import Attempt, Prover, gate
from atpx.counsel import transcript

from ..support import FakeCounsel, evidence_entries, live, stamped

_PASSING_PROBE = """import sys
for index in range(3):
    print(f'case{index} measured={index} target={index} diff=0')
sys.exit(0)
"""
_FAILING_PROBE = """import sys
print('case0 measured=1 target=2 diff=1')
print('mismatch', file=sys.stderr)
sys.exit(1)
"""
_VACUOUS_PROBE = "print('all good, trust me')\n"

_CLEAN_STDOUT = (
    "a measured=1 target=1 diff=0\nb measured=2 target=2 diff=0\nc measured=3 target=3 diff=0\n"
)


def probe_reply(probe: str) -> str:
    """A prover reply carrying one probe."""
    return json.dumps({"strategy": "direct check", "probe": probe})


def test_gate_demands_an_explicit_sys_exit() -> None:
    violation = gate("print('fine')", stdout=_CLEAN_STDOUT)
    assert violation is not None and "sys.exit" in violation


def test_gate_demands_three_measured_lines() -> None:
    violation = gate(_PASSING_PROBE, stdout="a measured=1 target=1 diff=0\nprose only\n")
    assert violation is not None and "measured lines" in violation


def test_gate_is_clean_on_a_disciplined_probe() -> None:
    assert gate(_PASSING_PROBE, stdout=_CLEAN_STDOUT) is None


def test_transcript_falls_back_to_the_json_payload() -> None:
    assert transcript(stamped()) == '{"ok": true}'


def test_prover_passes_on_the_first_try(root: Path) -> None:
    counsel = FakeCounsel(probe_reply(_PASSING_PROBE))
    attempt = Prover(counselor=counsel).attempt(
        live(root), slug="fresh", claim="probe", spec="Check n=3 cases."
    )
    assert isinstance(attempt, Attempt)
    assert attempt.passed and attempt.rounds == 1 and not attempt.violation
    blueprint = root / "research" / "math" / "fresh"
    assert (blueprint / "probes" / "probe.py").read_text() == _PASSING_PROBE
    (entry,) = evidence_entries(blueprint)
    assert entry["claim"] == "fresh/probe" and entry["exit_status"] == 0
    records = (blueprint / "attempts" / "probe.jsonl").read_text().splitlines()
    assert len(records) == 1 and json.loads(records[0])["violation"] == ""


def test_prover_repairs_a_failing_probe_then_passes(root: Path) -> None:
    counsel = FakeCounsel(probe_reply(_FAILING_PROBE), probe_reply(_PASSING_PROBE))
    attempt = Prover(counselor=counsel).attempt(
        live(root), slug="fresh", claim="probe", spec="Check the cases."
    )
    assert attempt.passed and attempt.rounds == 2
    feedback = counsel.calls[1][-1]
    assert feedback["role"] == "user" and "exit 1" in str(feedback["content"])
    records = (root / "research" / "math" / "fresh" / "attempts" / "probe.jsonl").read_text()
    assert len(records.splitlines()) == 2


def test_prover_fails_honestly_after_the_repair_budget(root: Path) -> None:
    counsel = FakeCounsel(probe_reply(_VACUOUS_PROBE))
    attempt = Prover(counselor=counsel).attempt(
        live(root), slug="fresh", claim="probe", spec="Check the cases.", repairs=1
    )
    assert not attempt.passed and attempt.rounds == 2
    assert "sys.exit" in attempt.violation
    assert len(counsel.calls) == 2


def test_prover_reads_an_unparseable_reply_as_no_probe(root: Path) -> None:
    counsel = FakeCounsel("not json at all")
    attempt = Prover(counselor=counsel).attempt(
        live(root), slug="fresh", claim="probe", spec="Check the cases.", repairs=0
    )
    assert not attempt.passed
    assert attempt.violation == "the reply carried no probe field"


def test_prover_tells_the_model_the_default_cap(root: Path) -> None:
    counsel = FakeCounsel(probe_reply(_PASSING_PROBE))
    Prover(counselor=counsel).attempt(live(root), slug="fresh", claim="probe", spec="Check.")
    (call,) = counsel.calls
    assert "killed at 120s wall clock" in str(call[1]["content"])


def test_prover_honors_an_explicit_probe_timeout(root: Path) -> None:
    slow_probe = f"import time\ntime.sleep(0.4)\n{_PASSING_PROBE}"
    counsel = FakeCounsel(probe_reply(slow_probe), probe_reply(slow_probe))
    starved = Prover(counselor=counsel).attempt(
        live(root), slug="fresh", claim="starved", spec="Check.", repairs=0, timeout=0.1
    )
    assert not starved.passed and "exit " in starved.violation
    granted = Prover(counselor=counsel).attempt(
        live(root), slug="fresh", claim="granted", spec="Check.", repairs=0, timeout=30.0
    )
    assert granted.passed
    assert "killed at 30s wall clock" in str(counsel.calls[1][1]["content"])


def test_prover_prompts_carry_the_tactics_and_the_json_hint(root: Path) -> None:
    (root / "research" / "math" / "TACTICS.md").write_text("Seed every generator.\n")
    counsel = FakeCounsel(probe_reply(_PASSING_PROBE))
    Prover(counselor=counsel).attempt(
        live(root), slug="fresh", claim="probe", spec="Check the cases."
    )
    (call,) = counsel.calls
    assert "Seed every generator." in str(call[0]["content"])
    assert 'example {"probe": "import sys\\n..."}' in str(call[1]["content"])


def test_prove_verb_resolves_the_spec_against_the_root(
    root: Path, monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> None:
    (root / "spec.md").write_text("Check three cases numerically.")
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))
    monkeypatch.setattr("atpx.counsel.prover.consult", FakeCounsel(probe_reply(_PASSING_PROBE)))
    summary = live(root).prove("fresh", "probe", spec="spec.md")
    assert summary["passed"] is True and summary["claim"] == "probe"
    assert summary["probe"] == "research/math/fresh/probes/probe.py"

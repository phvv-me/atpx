import json

import pytest
from flint import arb, fmpq
from pydantic import JsonValue

from atpx import is_ball_witness
from atpx.rigor import BallAudit, LabAudit, SmtAudit, witnesses


def ball_line(name: str = "octave-m1", *, verified: bool = True) -> str:
    """One printed ball witness line, as a probe would emit it."""
    return json.dumps(
        {
            "ball_certificate": {
                "name": name,
                "mid": "-0.02083",
                "rad": "1e-40",
                "verified": verified,
            }
        }
    )


def smt_line(name: str = "m2-forcing", *, result: str = "unsat") -> str:
    """One printed smt witness line, as a probe would emit it."""
    return json.dumps({"smt_certificate": {"name": name, "result": result, "logic": "QF_LRA"}})


def receipt_line(
    run_id: str = "9d3c1a77b2e40f5b", *, outcome: str = "passed", reason: str = ""
) -> str:
    """One printed trial receipt, exactly as an experiment harness emits it."""
    return json.dumps(
        {
            "trial_receipt": {
                "run_id": run_id,
                "outcome": outcome,
                "producer": "some-harness",
                "gates": [{"status": outcome, "reason": reason}],
                "reason": reason,
            }
        }
    )


def witness_record(capsys: pytest.CaptureFixture[str]) -> dict[str, JsonValue]:
    """The single ball witness printed during the test."""
    (line,) = capsys.readouterr().out.strip().splitlines()
    return json.loads(line)["ball_certificate"]


def test_ball_witness_verifies_an_enclosure_inside_the_tolerance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    value = arb(fmpq(-1, 64)) + arb(0, "1e-40")
    assert is_ball_witness("octave-m1", value, fmpq(-1, 64), tol=1e-30, prec=128)
    record = witness_record(capsys)
    assert record["verified"] is True and record["prec"] == 128
    assert record["target"] == "-1/64" and record["tol"] == 1e-30


def test_ball_witness_refuses_an_enclosure_leaking_past_the_tolerance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert not is_ball_witness("loose", arb(0, 1.0), 0, tol=0.5)
    assert witness_record(capsys)["verified"] is False


def test_ball_witness_refuses_a_wrong_midpoint(capsys: pytest.CaptureFixture[str]) -> None:
    assert not is_ball_witness("wrong", arb(1) + arb(0, "1e-40"), 0, tol=1e-30)
    assert witness_record(capsys)["verified"] is False


def test_witnesses_reads_only_well_formed_lines() -> None:
    output = "\n".join(
        [
            "prose",
            "{not json",
            '{"other": {"a": 1}}',
            ball_line("one"),
            ball_line("two", verified=False),
        ]
    )
    found = witnesses(output, key="ball_certificate")
    assert [line["name"] for line in found] == ["one", "two"]


def test_ball_audit_demands_at_least_one_witness() -> None:
    assert "no ball_certificate" in BallAudit().violation("cases passed\n")


def test_ball_audit_names_the_unverified_witnesses() -> None:
    output = "\n".join([ball_line("good"), ball_line("bad", verified=False)])
    violation = BallAudit().violation(output)
    assert "bad" in violation and "good" not in violation


def test_smt_audit_demands_unsat_and_calls_sat_a_counterexample() -> None:
    assert "no smt_certificate" in SmtAudit().violation("solver ran\n")
    assert SmtAudit().violation(smt_line()) == ""
    violation = SmtAudit().violation(smt_line("negation", result="sat"))
    assert "negation=sat" in violation and "counterexample" in violation


def test_lab_audit_passes_when_every_printed_trial_cleared_its_gates() -> None:
    output = f"loading\n{receipt_line('aaa')}\n{receipt_line('bbb')}\nsummary\n"
    assert LabAudit().violation(output) == ""
    assert [line["run_id"] for line in witnesses(output, key=LabAudit().key)] == ["aaa", "bbb"]


def test_lab_audit_refuses_output_carrying_no_receipt_at_all() -> None:
    assert LabAudit().violation("ran fine\n") == "no trial_receipt line printed"


@pytest.mark.parametrize("outcome", ["blocked", "failed"])
def test_lab_audit_refuses_a_trial_that_never_measured(outcome: str) -> None:
    """A withheld trial is not a checked claim, whichever way the framework withheld it."""
    violation = LabAudit().violation(receipt_line("ccc", outcome=outcome, reason="GPU busy"))
    assert "ccc" in violation and outcome in violation and "GPU busy" in violation

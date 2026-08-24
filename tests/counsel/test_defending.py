import json
from pathlib import Path

import pytest

from atpx import Certificate, Referral, Refuter
from atpx.counsel.defending import cases, covered, fallback, rebutted, targets
from atpx.counsel.probing import judged

from ..support import FakeCounsel, live, stamped

# The units-convention round, trimmed. The accepted defense answered none of the
# attack's quantities and exited 0 through its own failed-measurement branch.
_ATTACK_STDOUT = """B=1.000000 band=[0.900000,1.100000]
A_in=1.000000 -> R=1.000000 in_band=True
A_out=0.500000 -> R=0.500000 in_band=False
"""
_HOLLOW_DEFENSE = """import sys
rows = 0
print(f'case=audit_rows measured={rows} target=20 diff={rows - 20}')
print('case=kernel_norm measured=1.5e-07 target=1.5e-07 diff=0.0')
print('case=share_pair measured=0.5 target=0.5 diff=0.0')
if rows == 20:
    sys.exit(1)
else:
    sys.exit(0)
"""
_HOLLOW_STDOUT = """case=audit_rows measured=0 target=20 diff=-20
case=kernel_norm measured=1.5e-07 target=1.5e-07 diff=0.0
case=share_pair measured=0.5 target=0.5 diff=0.0
"""
_MATCHED_DEFENSE = """import sys
for name in ('B', 'band', 'A_in', 'A_out', 'R', 'in_band'):
    print(f'case={name} measured=1.0 target=1.0 diff=0.0')
sys.exit(0)
"""
_MATCHED_STDOUT = "".join(
    f"case={name} measured=1.0 target=1.0 diff=0.0\n"
    for name in ("B", "band", "A_in", "A_out", "R", "in_band")
)
_SWALLOWING_DEFENSE = """import sys
try:
    for name in ('B', 'band', 'A_in', 'A_out', 'R', 'in_band'):
        print(f'case={name} measured=1.0 target=1.0 diff=0.0')
except Exception:
    sys.exit(0)
sys.exit(0)
"""
_NAMED_ATTACK = """import sys
print('B=1.000000 band=0.900000')
print('A_in=1.000000 R=1.000000')
print('A_out=0.500000 R=0.500000')
sys.exit(0)
"""


def ran(stdout: str, exit_status: int = 0) -> Certificate:
    """A defense run certificate carrying the given output."""
    return stamped(claim="demo/defend-1-1", exit_status=exit_status).model_copy(
        update={"result": {"output": stdout}}
    )


def test_the_hollow_defense_passed_the_old_gate() -> None:
    assert judged(_HOLLOW_DEFENSE, ran(_HOLLOW_STDOUT)) == ""


def test_the_defense_gate_rejects_the_hollow_defense() -> None:
    violation = rebutted(_HOLLOW_DEFENSE, ran(_HOLLOW_STDOUT), attack=_ATTACK_STDOUT)
    assert "never measures" in violation
    assert "A_in" in violation and "A_out" in violation and "B" in violation


def test_a_defense_measuring_every_attack_quantity_counts() -> None:
    assert rebutted(_MATCHED_DEFENSE, ran(_MATCHED_STDOUT), attack=_ATTACK_STDOUT) == ""


def test_a_failing_defense_run_stays_refused() -> None:
    violation = rebutted(_MATCHED_DEFENSE, ran("boom", exit_status=1), attack=_ATTACK_STDOUT)
    assert violation.startswith("exit 1")


def test_an_except_handler_that_can_exit_zero_never_counts() -> None:
    violation = rebutted(_SWALLOWING_DEFENSE, ran(_MATCHED_STDOUT), attack=_ATTACK_STDOUT)
    assert "except handler" in violation


@pytest.mark.parametrize(
    ("handler_body", "violation"),
    [
        pytest.param("sys.exit()", "except handler", id="bare exit defaults to success"),
        pytest.param("sys.exit(code)", "except handler", id="a computed status could be zero"),
        pytest.param("sys.exit('broken')", None, id="a message exit is nonzero"),
        pytest.param("print('x')", None, id="other calls are not exits"),
    ],
)
def test_only_handlers_that_can_exit_zero_are_fallbacks(
    handler_body: str, violation: str | None
) -> None:
    source = f"import sys\ncode = 1\ntry:\n    pass\nexcept ValueError:\n    {handler_body}\n"
    if violation is None:
        assert fallback(source) is None
    else:
        assert violation in str(fallback(source))


def test_targets_reads_case_values_and_named_keys_but_never_grammar() -> None:
    stdout = "case=alpha measured=1 target=1 diff=0\nbeta=2.5 -> E[2]=3\nprose only\n"
    assert targets(stdout) == {"alpha", "beta"}


def test_cases_reads_only_case_tokens() -> None:
    assert cases(_HOLLOW_STDOUT) == {"audit_rows", "kernel_norm", "share_pair"}
    assert cases(_ATTACK_STDOUT) == set()


def test_coverage_is_vacuous_when_the_attack_names_nothing() -> None:
    assert covered("case=own measured=1 target=1 diff=0", attack="prose, no measures") is None


def attack_reply(probe: str) -> str:
    """A refuter reply carrying one counterexample probe."""
    return json.dumps({"verdict": "FATAL", "reason": "referee", "counterexample_probe": probe})


def defense_reply(probe: str) -> str:
    """A defender reply carrying one defense probe."""
    return json.dumps({"reason": "audit", "defense_probe": probe})


def test_a_hollow_defense_now_loses_the_bout(root: Path) -> None:
    counsel = FakeCounsel(attack_reply(_NAMED_ATTACK), defense_reply(_HOLLOW_DEFENSE))
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=1, rounds=1)
    assert isinstance(referral, Referral)
    assert referral.verdict == "FATAL candidate"
    attack, defense = referral.episodes
    assert attack.demonstrated and not defense.demonstrated
    assert "never measures" in defense.detail


def test_a_matched_defense_still_rebuts_the_bout(root: Path) -> None:
    counsel = FakeCounsel(attack_reply(_NAMED_ATTACK), defense_reply(_MATCHED_DEFENSE))
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=1, rounds=1)
    assert referral.verdict == "survived"
    attack, defense = referral.episodes
    assert attack.demonstrated and defense.demonstrated

import json
from pathlib import Path

import pytest

from atpx import Referral, Refuter, Status

from ..support import FakeCounsel, evidence_entries, live

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
_FIRST_ATTACK = "refute-1-1"
_SURVIVED = "survived"


def attack_reply(probe: str, *, verdict: str = "NONE") -> str:
    """A refuter reply carrying one counterexample probe and an emitted verdict."""
    return json.dumps(
        {"verdict": verdict, "reason": "referee notes", "counterexample_probe": probe}
    )


def defense_reply(probe: str) -> str:
    """A defender reply carrying one defense probe."""
    return json.dumps({"reason": "scope audit", "defense_probe": probe})


def test_refuter_reads_a_probeless_reply_as_not_demonstrating(root: Path) -> None:
    counsel = FakeCounsel(attack_reply(""))
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=1, rounds=1)
    assert isinstance(referral, Referral)
    (episode,) = referral.episodes
    assert not episode.demonstrated and episode.stdout == ""
    assert episode.detail == "no counterexample probe emitted"


def test_an_undefended_demonstration_loses_the_bout(root: Path) -> None:
    counsel = FakeCounsel(attack_reply(_PASSING_PROBE), defense_reply(""))
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=1, rounds=1)
    assert referral.verdict == "FATAL candidate"
    attack, defense = referral.episodes
    assert attack.demonstrated and attack.claim == _FIRST_ATTACK
    assert not defense.demonstrated and defense.claim == "defend-1-1"
    entries = evidence_entries(root / "research" / "math" / "demo")
    assert entries[-1]["claim"] == f"demo/{_FIRST_ATTACK}" and entries[-1]["exit_status"] == 0


def test_a_rebutted_boss_must_attack_again(root: Path) -> None:
    counsel = FakeCounsel(
        attack_reply(_PASSING_PROBE),
        defense_reply(_PASSING_PROBE),
        attack_reply(_FAILING_PROBE),
    )
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=1, rounds=2)
    assert referral.verdict == _SURVIVED
    assert [episode.claim for episode in referral.episodes] == [
        _FIRST_ATTACK,
        "defend-1-1",
        "refute-1-2",
    ]
    assert [episode.demonstrated for episode in referral.episodes] == [True, True, False]
    rebuttal_feedback = counsel.calls[2][-1]
    assert "rebutted your attack" in str(rebuttal_feedback["content"])


def test_a_lost_bout_stops_the_ladder(root: Path) -> None:
    counsel = FakeCounsel(
        attack_reply(_FAILING_PROBE),
        attack_reply(_PASSING_PROBE),
        defense_reply(_VACUOUS_PROBE),
    )
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=4, rounds=1)
    assert referral.verdict == "FATAL candidate"
    assert [episode.claim for episode in referral.episodes] == [
        _FIRST_ATTACK,
        "refute-2-1",
        "defend-2-1",
    ]
    assert len(counsel.calls) == 3


def test_refuter_survives_non_demonstrating_attacks(root: Path) -> None:
    counsel = FakeCounsel(
        attack_reply(_FAILING_PROBE, verdict="FATAL"),
        attack_reply(_VACUOUS_PROBE, verdict="FATAL"),
    )
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=2, rounds=1)
    assert referral.verdict == _SURVIVED
    assert [episode.demonstrated for episode in referral.episodes] == [False, False]


def test_a_failed_swing_feeds_the_boss_its_violation(root: Path) -> None:
    counsel = FakeCounsel(attack_reply(_VACUOUS_PROBE), attack_reply(_FAILING_PROBE))
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=1, rounds=2)
    assert referral.verdict == _SURVIVED
    retry_feedback = counsel.calls[1][-1]
    assert "did not count" in str(retry_feedback["content"])


def test_refuter_drafts_a_judgment_with_defense_states(root: Path) -> None:
    counsel = FakeCounsel(
        attack_reply(_PASSING_PROBE),
        defense_reply(_PASSING_PROBE),
        attack_reply(_FAILING_PROBE),
    )
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=1, rounds=2)
    draft = root / referral.draft
    assert draft.parent.name == "judgments" and draft.name.startswith("draft-")
    text = draft.read_text()
    assert text.rstrip().endswith("semantic review by the mathematician required before settle.")
    assert "rebutting" in text and _FIRST_ATTACK in text and "defend-1-1" in text


def test_refuter_never_settles_the_node_itself(root: Path) -> None:
    counsel = FakeCounsel(attack_reply(_PASSING_PROBE), defense_reply(""))
    space = live(root)
    Refuter(counselor=counsel).fanout(space, "demo", n=1, rounds=1)
    node = space.nodes.find("demo")
    assert node.status is Status.OPEN
    assert all(entry.who != "settle" for entry in node.log)


def test_refuter_cycles_the_attack_lanes(root: Path) -> None:
    counsel = FakeCounsel(attack_reply(_FAILING_PROBE))
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=5, rounds=1)
    models = [episode.model for episode in referral.episodes]
    assert models[4] == models[0] and len(counsel.calls) == 5


def test_refute_verb_reports_compactly_without_stdout_tails(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("atpx.counsel.refuter.consult", FakeCounsel(attack_reply(_FAILING_PROBE)))
    summary = live(root).refute("demo", n=1, rounds=1)
    assert summary["verdict"] == _SURVIVED and summary["slug"] == "demo"
    episodes = summary["episodes"]
    assert isinstance(episodes, list)
    (episode,) = episodes
    assert isinstance(episode, dict)
    assert "stdout" not in episode and episode["demonstrated"] is False


def test_a_gate_fumble_repairs_privately_inside_one_move(root: Path) -> None:
    counsel = FakeCounsel(attack_reply(_VACUOUS_PROBE), attack_reply(_FAILING_PROBE))
    referral = Refuter(counselor=counsel).fanout(live(root), "demo", n=1, rounds=1, tries=2)
    assert referral.verdict == _SURVIVED
    (episode,) = referral.episodes
    assert episode.claim == _FIRST_ATTACK and not episode.demonstrated
    assert len(counsel.calls) == 2
    repair_feedback = counsel.calls[1][-1]
    assert "Repair it" in str(repair_feedback["content"])


def test_fresh_context_restarts_each_round_from_the_node(root: Path) -> None:
    counsel = FakeCounsel(
        attack_reply(_PASSING_PROBE),
        defense_reply(_PASSING_PROBE),
        attack_reply(_FAILING_PROBE),
    )
    referral = Refuter(counselor=counsel).fanout(
        live(root), "demo", n=1, rounds=2, context="fresh"
    )
    assert referral.verdict == _SURVIVED
    assert len(counsel.calls[2]) == 3
    assert "rebutted your attack" in str(counsel.calls[2][-1]["content"])

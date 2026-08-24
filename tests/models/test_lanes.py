from pathlib import Path

import pytest

from atpx import Lanes, ModelLane, Workspace

_LUNA = "openai/gpt-5.6-luna"
_TEMPERATURE = "temperature"


def test_a_reasoning_lane_omits_sampling() -> None:
    lane = ModelLane(model=_LUNA)
    assert lane.sampling() == {}
    assert Lanes().prover.sampling() == {_TEMPERATURE: 1.0, "top_p": 0.95}


def test_default_ladder_reasons_and_the_prover_does_not() -> None:
    lanes = Lanes()
    assert not lanes.prover.reasoning
    assert [lane.reasoning for lane in lanes.ladder] == [False, False, True, True]


def test_lanes_override_from_the_models_table(root: Path) -> None:
    (root / "atpx.toml").write_text(
        """[workspace]

[models]
prover = "x/custom"
ladder = [
    "a/one",
    { model = "b/two-pro", timeout = 900, max_tokens = 32000 },
]
"""
    )
    space = Workspace(root)
    assert space.lanes.prover.model == "x/custom"
    assert space.lanes.prover.temperature == 1.0 and space.lanes.prover.top_p == 0.95
    assert [lane.model for lane in space.lanes.ladder] == ["a/one", "b/two-pro"]
    assert all(lane.temperature is None for lane in space.lanes.ladder)
    assert all(lane.reasoning for lane in space.lanes.ladder)
    plain, pro = space.lanes.ladder
    assert plain.timeout is None and plain.max_tokens is None
    assert pro.timeout == 900 and pro.max_tokens == 32000


def test_lanes_refuse_a_malformed_ladder_entry() -> None:
    with pytest.raises(ValueError, match="model id or a lane table"):
        Lanes.configured({"ladder": [7]})

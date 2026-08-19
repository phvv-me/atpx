import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import SeedSweep, seed_sensitivity

seeds_strategy = st.integers(min_value=0, max_value=10_000)
seed_lists = st.lists(seeds_strategy, min_size=1, max_size=8, unique=True)


@given(seed_lists)
def test_a_constant_probe_is_stable(seeds: list[int]) -> None:
    sweep = seed_sensitivity(lambda seed: 1.5, seeds)
    assert isinstance(sweep, SeedSweep)
    assert sweep.stable and sweep.spread == 0.0
    assert set(sweep.outcomes) == set(seeds)


@given(seed_lists.filter(lambda seeds: len(seeds) >= 2))
def test_a_seed_dependent_probe_is_flagged(seeds: list[int]) -> None:
    sweep = seed_sensitivity(float, seeds)
    assert not sweep.stable
    assert sweep.spread == max(seeds) - min(seeds)


def test_seed_sensitivity_requires_at_least_one_seed() -> None:
    with pytest.raises(ValueError, match="at least one seed"):
        seed_sensitivity(float, [])

from collections.abc import Callable, Sequence

from patos import FrozenModel


class SeedSweep(FrozenModel):
    """Outcome of one probe under many seeds; a nonzero spread is a refutation lead."""

    outcomes: dict[int, float]
    spread: float

    @property
    def stable(self) -> bool:
        """Whether every seed produced the same outcome."""
        return self.spread == 0.0


def seed_sensitivity(fn: Callable[[int], float], seeds: Sequence[int]) -> SeedSweep:
    """Run a probe under every seed and report the outcome spread.

    fn: the probe, seed in, numeric verdict out.
    seeds: the seeds to sweep, at least one.
    """
    if not seeds:
        raise ValueError("seed_sensitivity needs at least one seed")
    outcomes = {seed: fn(seed) for seed in seeds}
    return SeedSweep(outcomes=outcomes, spread=max(outcomes.values()) - min(outcomes.values()))

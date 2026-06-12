from collections.abc import Callable, Sequence
from itertools import product

import flint

from .base import FrozenModel


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


def boundary_ties(basis: Sequence[Sequence[int]], radius: int = 1) -> list[tuple[float, ...]]:
    """Dyadic tie points of the lattice spanned by an integer basis.

    Every returned point is `v / 2` for a nonzero lattice vector `v` whose
    integer coefficients range over `[-radius, radius]`, so it sits exactly
    halfway between the origin and `v` and every coordinate is exactly
    representable in binary floating point. A decoder fed these must break the
    tie deterministically instead of hoping rounding hides it.

    basis: the generator matrix, one basis vector per row.
    radius: how far the integer coefficients range.
    """
    dimension = len(basis[0])
    ties = set()
    for coefficients in product(range(-radius, radius + 1), repeat=len(basis)):
        vector = tuple(
            sum(c * row[axis] for c, row in zip(coefficients, basis, strict=True))
            for axis in range(dimension)
        )
        if any(vector):
            ties.add(tuple(x / 2 for x in vector))
    return sorted(ties)


def precision_tilt(
    points: Sequence[Sequence[float]], epsilons: Sequence[float]
) -> dict[float, list[tuple[float, ...]]]:
    """Tilted copies of the points, one batch per epsilon in the ladder.

    Each batch shifts every coordinate by `+epsilon`, probing verdicts that only
    hold at exact precision. A claim that flips under a tilt of `2**-40` was
    resting on a tie, not on mathematics.

    points: the probe points.
    epsilons: the tilt ladder, for example `(2**-20, 2**-30, 2**-40)`.
    """
    return {
        epsilon: [tuple(x + epsilon for x in point) for point in points] for epsilon in epsilons
    }


class Rederivation(FrozenModel):
    """Verdict on whether two integer bases generate the same lattice."""

    same_lattice: bool
    integral: bool
    determinant: str

    @classmethod
    def of(cls, transform: flint.fmpq_mat) -> Rederivation:
        """Judge a basis-change matrix: integral with determinant of magnitude one."""
        entries = [
            transform[row, column]
            for row in range(transform.nrows())
            for column in range(transform.ncols())
        ]
        integral = all(entry.q == 1 for entry in entries)
        determinant = transform.det()
        return cls(
            same_lattice=integral and determinant in (1, -1),
            integral=integral,
            determinant=str(determinant),
        )


def rederive(first: Sequence[Sequence[int]], second: Sequence[Sequence[int]]) -> Rederivation:
    """Check exactly whether two integer bases span the same lattice.

    The bases agree exactly when `U = second @ first^-1` is integral with
    `|det U| = 1`. Everything runs over exact rationals through flint, so the
    verdict carries no floating-point doubt; a singular reference basis raises.

    first: the reference basis, one vector per row.
    second: the independently derived basis to compare.
    """
    reference = flint.fmpq_mat(flint.fmpz_mat([list(row) for row in first]))
    derived = flint.fmpq_mat(flint.fmpz_mat([list(row) for row in second]))
    return Rederivation.of(derived * reference.inv())

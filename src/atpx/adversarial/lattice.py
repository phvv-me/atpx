from collections.abc import Sequence
from itertools import product


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
        vector = (
            *(
                sum(c * row[axis] for c, row in zip(coefficients, basis, strict=True))
                for axis in range(dimension)
            ),
        )
        if any(vector):
            ties.add((*(x / 2 for x in vector),))
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
        epsilon: [(*(x + epsilon for x in point),) for point in points] for epsilon in epsilons
    }

from collections.abc import Sequence

import flint
from patos import FrozenModel


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


def rederive(first: Sequence[Sequence[int]], *, second: Sequence[Sequence[int]]) -> Rederivation:
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

from collections.abc import Iterable

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import Rederivation, rederive

entries = st.integers(min_value=-4, max_value=4)
vectors = st.lists(entries, min_size=2, max_size=2)
bases = st.lists(vectors, min_size=2, max_size=2)
nonsingular = bases.filter(lambda b: b[0][0] * b[1][1] - b[0][1] * b[1][0] != 0)


@st.composite
def unimodular(draw: st.DrawFn) -> list[list[int]]:
    """A 2x2 unimodular integer matrix built from elementary row operations."""
    matrix = [[1, 0], [0, 1]]
    for _ in range(draw(st.integers(min_value=1, max_value=4))):
        source = draw(st.integers(min_value=0, max_value=1))
        factor = draw(st.integers(min_value=-3, max_value=3))
        target = 1 - source
        pairs = zip(matrix[target], matrix[source], strict=True)
        matrix[target] = [a + factor * b for a, b in pairs]
    if draw(st.booleans()):
        matrix.reverse()
    return matrix


def matmul(left: Iterable[Iterable[int]], *, right: list[list[int]]) -> list[list[int]]:
    """Integer matrix product, rows of `left` against columns of `right`."""
    columns = list(zip(*right, strict=True))
    return [
        [sum(a * b for a, b in zip(row, column, strict=True)) for column in columns]
        for row in left
    ]


@given(basis=nonsingular, transform=unimodular())
def test_a_unimodular_change_of_basis_keeps_the_lattice(
    basis: list[list[int]], *, transform: list[list[int]]
) -> None:
    verdict = rederive(basis, second=matmul(transform, right=basis))
    assert isinstance(verdict, Rederivation)
    assert verdict.same_lattice and verdict.integral


def test_a_scaled_basis_is_a_proper_sublattice() -> None:
    verdict = rederive([[1, 0], [0, 1]], second=[[2, 0], [0, 1]])
    assert not verdict.same_lattice and verdict.integral and verdict.determinant == "2"


def test_a_rational_transform_is_not_integral() -> None:
    verdict = rederive([[2, 0], [0, 2]], second=[[1, 0], [0, 2]])
    assert not verdict.same_lattice and not verdict.integral


def test_a_singular_reference_basis_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        rederive([[1, 1], [1, 1]], second=[[1, 0], [0, 1]])

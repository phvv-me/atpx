import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx.adversarial import boundary_ties, precision_tilt, rederive, seed_sensitivity

entries = st.integers(min_value=-4, max_value=4)
vectors = st.lists(entries, min_size=2, max_size=2)
bases = st.lists(vectors, min_size=2, max_size=2)
nonsingular = bases.filter(lambda b: b[0][0] * b[1][1] - b[0][1] * b[1][0] != 0)
seeds_strategy = st.integers(min_value=0, max_value=10_000)
seed_lists = st.lists(seeds_strategy, min_size=1, max_size=8, unique=True)


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


def matmul(left: list[list[int]], right: list[list[int]]) -> list[list[int]]:
    """Integer matrix product, rows of `left` against columns of `right`."""
    columns = list(zip(*right, strict=True))
    return [
        [sum(a * b for a, b in zip(row, column, strict=True)) for column in columns]
        for row in left
    ]


@given(seed_lists)
def test_a_constant_probe_is_stable(seeds: list[int]) -> None:
    sweep = seed_sensitivity(lambda seed: 1.5, seeds)
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


@given(nonsingular)
def test_boundary_ties_are_dyadic_nonzero_midpoints(basis: list[list[int]]) -> None:
    ties = boundary_ties(basis)
    for tie in ties:
        doubled = [2 * x for x in tie]
        assert all(x == int(x) for x in doubled)
        assert any(doubled)
    for row in basis:
        if any(row):
            assert tuple(x / 2 for x in row) in ties


def test_boundary_ties_skip_combinations_that_cancel_to_the_origin() -> None:
    assert (0.0, 0.0) not in boundary_ties([[1, 0], [-1, 0]])


@given(
    st.lists(st.lists(st.floats(-8, 8, allow_nan=False), min_size=2, max_size=2), max_size=4),
    st.lists(st.sampled_from([2**-10, 2**-20, 2**-40]), min_size=1, max_size=3, unique=True),
)
def test_precision_tilt_shifts_every_coordinate_exactly(
    points: list[list[float]], epsilons: list[float]
) -> None:
    tilted = precision_tilt(points, epsilons)
    assert list(tilted) == epsilons
    for epsilon in epsilons:
        assert tilted[epsilon] == [tuple(x + epsilon for x in point) for point in points]


@given(nonsingular, unimodular())
def test_a_unimodular_change_of_basis_keeps_the_lattice(
    basis: list[list[int]], transform: list[list[int]]
) -> None:
    verdict = rederive(basis, matmul(transform, basis))
    assert verdict.same_lattice and verdict.integral


def test_a_scaled_basis_is_a_proper_sublattice() -> None:
    verdict = rederive([[1, 0], [0, 1]], [[2, 0], [0, 1]])
    assert not verdict.same_lattice and verdict.integral and verdict.determinant == "2"


def test_a_rational_transform_is_not_integral() -> None:
    verdict = rederive([[2, 0], [0, 2]], [[1, 0], [0, 2]])
    assert not verdict.same_lattice and not verdict.integral


def test_a_singular_reference_basis_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        rederive([[1, 1], [1, 1]], [[1, 0], [0, 1]])

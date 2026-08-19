from hypothesis import given
from hypothesis import strategies as st

from atpx import boundary_ties, precision_tilt

entries = st.integers(min_value=-4, max_value=4)
vectors = st.lists(entries, min_size=2, max_size=2)
bases = st.lists(vectors, min_size=2, max_size=2)
nonsingular = bases.filter(lambda b: b[0][0] * b[1][1] - b[0][1] * b[1][0] != 0)


@given(nonsingular)
def test_boundary_ties_are_dyadic_nonzero_midpoints(basis: list[list[int]]) -> None:
    ties = boundary_ties(basis)
    for tie in ties:
        doubled = [2 * x for x in tie]
        assert all(x == int(x) for x in doubled)
        assert any(doubled)
    for row in basis:
        if any(row):
            assert (*(x / 2 for x in row),) in ties


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
        assert tilted[epsilon] == [(*(x + epsilon for x in point),) for point in points]

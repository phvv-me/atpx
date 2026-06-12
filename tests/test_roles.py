import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx.roles import GRANTS, SETTLED, Role, RoleError, Status, authorize

roles = st.sampled_from(Role)
statuses = st.sampled_from(Status)


@given(roles, statuses)
def test_authorize_matches_the_grants_table_exactly(role: Role, status: Status) -> None:
    if status in GRANTS[role]:
        authorize(role, status)
    else:
        with pytest.raises(RoleError):
            authorize(role, status)


@given(statuses)
def test_only_the_refuter_settles_sketched_or_refuted(status: Status) -> None:
    granters = {role for role in Role if status in GRANTS[role]}
    if status in (Status.SKETCHED, Status.REFUTED):
        assert granters == {Role.REFUTER}
    if status is Status.VERIFIED:
        assert granters == {Role.FORMALIZER}


def test_settled_statuses_are_the_terminal_rungs() -> None:
    assert {Status.SKETCHED, Status.REFUTED, Status.VERIFIED, Status.ABANDONED} == SETTLED
    assert Status.OPEN not in SETTLED
    assert Status.IN_PROGRESS not in SETTLED

import pytest

from atpx.support import drive


async def value() -> int:
    return 41 + 1


async def nested() -> int:
    """Drive a second coroutine from inside a running loop, which must be refused."""
    return drive(value())


def test_drive_runs_a_coroutine_to_completion() -> None:
    assert drive(value()) == 42


def test_drive_refuses_nested_event_loops() -> None:
    with pytest.raises(RuntimeError, match="active event loop"):
        drive(nested())

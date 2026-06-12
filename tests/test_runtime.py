import asyncio

import pytest

from atpx.runtime import drive


async def value() -> int:
    return 41 + 1


def test_drive_runs_a_coroutine_to_completion() -> None:
    assert drive(value()) == 42


def test_drive_refuses_nested_event_loops() -> None:
    async def nested() -> int:
        return drive(value())

    with pytest.raises(RuntimeError, match="active event loop"):
        asyncio.run(nested())

import asyncio
from collections.abc import Sequence


class SleepyRunner:
    """A runner that outlives any reasonable timeout."""

    async def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        await asyncio.sleep(60)
        return 0, "never"

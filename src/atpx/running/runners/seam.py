from collections.abc import Sequence
from typing import Protocol


class CommandRunner(Protocol):
    """How claim and build commands execute."""

    async def __call__(self, argv: Sequence[str]) -> tuple[int, str]: ...

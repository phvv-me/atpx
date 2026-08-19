from collections.abc import Sequence

from patos import Model


class FakeRunner(Model):
    """Claim runner double recording argv and replying with a canned line."""

    exit_status: int = 0
    output: str = '{"passed": true}\n'
    calls: list[list[str]] = []

    async def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        self.calls.append(list(argv))
        return self.exit_status, self.output

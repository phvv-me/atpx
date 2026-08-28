import asyncio
from collections.abc import Sequence
from importlib.metadata import version as package_version
from pathlib import Path

from ..blueprint.manifest import Blueprint
from ..core.certificate import Certificate
from ..support.naming import Naming
from .payload import Capture
from .runners.seam import CommandRunner

_RERUN_LIMIT = 4


class Running:
    """Capture-first execution: run commands through one runner, stamp certificates.

    The (runner, root) pair every run needs travels here once, so the verbs
    above read as their algorithm: attempt a claim, sweep several, or bound an
    arbitrary command under the hard wall-clock cap.
    """

    def __init__(self, runner: CommandRunner, root: Path) -> None:
        """runner: the command executor.

        root: the workspace root commands run from and certificates stamp.
        """
        self.runner = runner
        self.root = root

    async def attempted(
        self,
        blueprint: Blueprint,
        claim: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Run one claim command and stamp its certificate.

        blueprint: the loaded claim manifest.
        claim: the claim name to run.
        seed: RNG seed to record when the claim script used one.
        timeout: hard wall-clock cap in seconds.
        """
        exit_status, output = await self.bounded(blueprint.command(claim), timeout)
        return Certificate.stamp(
            claim=f"{blueprint.slug}/{claim}",
            result=Capture(blueprint.directory).payload(output),
            engine=Naming.NAME,
            engine_version=package_version(Naming.NAME),
            exit_status=exit_status,
            seed=seed,
            root=self.root,
        )

    async def bounded(self, argv: Sequence[str], timeout: float | None) -> tuple[int, str]:
        """Run one command under a hard wall-clock cap.

        Expiry returns exit 124 in the shell timeout convention instead of
        hanging the loop, per the house rule that no call may block a session.

        argv: the command tokens.
        timeout: seconds before giving up, None to wait forever.
        """
        try:
            return await self.__ran(argv, timeout)
        except TimeoutError:
            return 124, f"timed out after {timeout}s"

    async def swept(self, blueprint: Blueprint, claims: Sequence[str]) -> dict[str, Certificate]:
        """Re-run claims concurrently, at most four in flight.

        A `TaskGroup` rather than a bare gather, so an unexpected fault in one
        claim, or a ctrl-c reaching the loop, cancels the siblings and waits
        for them instead of abandoning half-finished subprocesses.

        blueprint: the loaded claim manifest.
        claims: the claim names this host can run.
        """
        semaphore = asyncio.Semaphore(_RERUN_LIMIT)

        async def turn(claim: str) -> Certificate:
            async with semaphore:
                return await self.attempted(blueprint, claim)

        async with asyncio.TaskGroup() as group:
            tasks = {claim: group.create_task(turn(claim)) for claim in claims}
        return {claim: task.result() for claim, task in tasks.items()}

    async def __ran(self, argv: Sequence[str], timeout: float | None) -> tuple[int, str]:
        """The command under its cap, an overdue call raising `TimeoutError` on exit."""
        async with asyncio.timeout(timeout):
            return await self.runner(argv)

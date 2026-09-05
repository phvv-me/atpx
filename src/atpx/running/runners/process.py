import asyncio
from collections.abc import Sequence
from pathlib import Path
from shutil import which
from typing import NoReturn

from patos import FrozenModel
from psutil import NoSuchProcess, wait_procs
from psutil import Process as SystemProcess


def _kill_tree(pid: int) -> None:
    """Kill one launcher and every descendant it created."""
    try:
        parent = SystemProcess(pid)
        descendants = parent.children(recursive=True)
        parent.kill()
    except NoSuchProcess:
        return
    for descendant in reversed(descendants):
        try:
            descendant.kill()
        except NoSuchProcess:
            continue
    wait_procs(descendants, timeout=5)


class ProcessRunner(FrozenModel):
    """Runs claim commands as subprocesses from the workspace root, behind an optional launcher.

    The launcher is whatever the workspace declares as `[workspace] runner`, a command
    prefix that puts every claim inside the environment that workspace provisions for
    itself. Empty by default, so a plain checkout runs its claims on the interpreter
    already activated around atpx and needs no other tool installed.

    root: the workspace root commands run from.
    launcher: the prefix tokens every claim command is handed to.
    """

    root: Path
    launcher: Sequence[str] = ()

    async def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        """Execute the launched command from the root and return (exit status, combined output).

        A caller's timeout cancels this call from outside (`Running.bounded`'s wall-clock
        cap), so cancellation here must kill the child itself, or a timed-out claim would
        leave its launcher orphaned in the background.
        """
        command = [*self.launcher, *argv]
        command[0] = which(command[0]) or command[0]
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await process.communicate()
        except asyncio.CancelledError:
            await self.__killed(process)
        return process.returncode or 0, stdout.decode("utf-8")

    @staticmethod
    async def __killed(process: asyncio.subprocess.Process) -> NoReturn:
        """Kill an orphaned child, drain its pipes, then let cancellation propagate."""
        _kill_tree(process.pid)
        await process.communicate()
        raise

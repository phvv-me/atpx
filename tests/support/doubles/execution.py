import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from patos import FrozenModel


class ExecRunner(FrozenModel):
    """Runs claim argv as a real subprocess, `python` mapped to this interpreter.

    The counsel tests never mock the certificate path: tiny real probes run
    here and land as genuinely stamped certificates.
    """

    root: Path

    async def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        command = [sys.executable if token == "python" else token for token in argv]
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=self.root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await process.communicate()
        return process.returncode or 0, stdout.decode()

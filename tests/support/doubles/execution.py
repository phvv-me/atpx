import sys
from collections.abc import Sequence
from pathlib import Path

from patos import FrozenModel

from atpx.running import ProcessRunner


class ExecRunner(FrozenModel):
    """Runs claim argv as a real subprocess, `python` mapped to this interpreter.

    The counsel tests never mock the certificate path: tiny real probes run
    here and land as genuinely stamped certificates.
    """

    root: Path

    async def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        command = [sys.executable if token == "python" else token for token in argv]
        return await ProcessRunner(root=self.root)(command)

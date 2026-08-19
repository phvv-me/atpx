from pathlib import Path

from atpx import Workspace

from .doubles.execution import ExecRunner


def live(root: Path) -> Workspace:
    """A workspace whose probes run as real subprocesses."""
    return Workspace(root, runner=ExecRunner(root=root))

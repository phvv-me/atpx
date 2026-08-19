from pathlib import Path

from .facade import Workspace


def workspace(root: str | Path | None = None) -> Workspace:
    """Open the workspace at `root`, discovering it from `ATPX_ROOT` or the cwd when omitted.

    `root` may name the root itself or any directory inside it, since discovery walks
    upward from wherever it is pointed.
    """
    return Workspace(Path(root) if root else None)

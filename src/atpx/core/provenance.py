import socket
from pathlib import Path

from patos import FrozenModel
from plumbum import CommandNotFound, ProcessExecutionError, local


class Provenance(FrozenModel):
    """Where and when a certifying run happened, captured once and never reconstructed."""

    hostname: str
    device: str
    seed: int | None = None
    git_rev: str
    timestamp: str

    @staticmethod
    def git_revision(root: Path) -> str:
        """Short git revision of `root`, suffixed `+dirty` when the tree has changes.

        root: directory inside the repository to describe.
        """
        git = local["git"]["-C", str(root)]
        try:
            revision, dirty = (
                git("rev-parse", "--short", "HEAD").strip(),
                git("status", "--porcelain").strip(),
            )
        except ProcessExecutionError, CommandNotFound:
            return "unknown"
        return f"{revision}+dirty" if dirty else revision

    @staticmethod
    def short_hostname() -> str:
        """This host's name up to the first dot, the evidence-file key."""
        return socket.gethostname().split(".")[0]

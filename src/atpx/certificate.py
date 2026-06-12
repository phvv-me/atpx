import platform
import socket
from datetime import UTC, datetime
from pathlib import Path

from plumbum import CommandNotFound, ProcessExecutionError, local
from pydantic import JsonValue

from .base import FrozenModel


def short_hostname() -> str:
    """This host's name up to the first dot, the evidence-file key."""
    return socket.gethostname().split(".")[0]


def git_revision(root: Path) -> str:
    """Short git revision of `root`, suffixed `+dirty` when the tree has changes.

    root: directory inside the repository to describe.
    """
    git = local["git"]["-C", str(root)]
    try:
        revision = git("rev-parse", "--short", "HEAD").strip()
        dirty = git("status", "--porcelain").strip()
    except ProcessExecutionError, CommandNotFound:
        return "unknown"
    return f"{revision}+dirty" if dirty else revision


class Certificate(FrozenModel):
    """The one contract: every atpx operation returns one of these, never a naked result."""

    claim: str
    result: JsonValue
    engine: str
    engine_version: str
    hostname: str
    device: str
    seed: int | None = None
    git_rev: str
    timestamp: str
    exit_status: int

    @property
    def ok(self) -> bool:
        """Whether the operation exited cleanly."""
        return self.exit_status == 0

    def __str__(self) -> str:
        return self.model_dump_json(indent=2)

    @classmethod
    def stamp(
        cls,
        *,
        claim: str,
        result: JsonValue,
        engine: str,
        engine_version: str,
        exit_status: int = 0,
        seed: int | None = None,
        root: Path | None = None,
    ) -> Certificate:
        """Build a certificate with provenance captured now, never reconstructed later.

        claim: claim text or id being certified.
        result: payload the operation produced.
        engine: name of the engine that ran.
        engine_version: its version string.
        exit_status: process or agreement exit code, zero means clean.
        seed: RNG seed when the operation used one.
        root: repository to stamp the git revision from, defaults to the cwd.
        """
        return cls(
            claim=claim,
            result=result,
            engine=engine,
            engine_version=engine_version,
            hostname=short_hostname(),
            device=f"{platform.system()}-{platform.machine()}",
            seed=seed,
            git_rev=git_revision(root or Path.cwd()),
            timestamp=datetime.now(UTC).isoformat(),
            exit_status=exit_status,
        )

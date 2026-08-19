import stat
from pathlib import Path


def script(directory: Path, name: str, *, body: str) -> Path:
    """Write an executable POSIX shell script on disk and return its path."""
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path

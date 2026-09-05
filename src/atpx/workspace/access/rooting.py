import os
import tomllib
from pathlib import Path

from ...support.naming import Naming

_ROOT_VARIABLE = f"{Naming.NAME.upper()}_ROOT"


def _is_rooted(candidate: Path) -> bool:
    """Whether `candidate` holds a manifest declaring a `[workspace]` table.

    The one test that separates a workspace root from a blueprint directory, which
    carries the same filename holding only `[claims]`.

    candidate: the directory to test.
    """
    manifest = candidate / Naming.CONFIG
    return manifest.exists() and "workspace" in tomllib.loads(manifest.read_text(encoding="utf-8"))


def find_roots(start: Path | None = None) -> list[Path]:
    """Every workspace at or below `start`, the resolved root first and the rest sorted.

    A monorepo keeps one workspace per project (`research/thoughtlens`, `research/bale`)
    beneath a root workspace of its own, and a lint that has to answer whether every
    mathematical idea is settled must see all of them from wherever it was fired. Nested
    workspaces are still walked into, since a project may itself hold sub-projects, while
    a blueprint's own `[claims]` manifest is never mistaken for one.

    start: where to begin, the resolved root when omitted.
    """
    home = find_root(start)
    found = {
        manifest.parent.resolve()
        for manifest in home.rglob(f"*/{Naming.CONFIG}")
        if _is_rooted(manifest.parent)
    }
    return [home, *sorted(found - {home})]


def find_root(start: Path | None = None) -> Path:
    """The workspace root: `ATPX_ROOT` when set, else walking up from `start` or the cwd.

    The environment override pins every atpx invocation to one workspace, so a
    verb fired from anywhere in a monorepo cannot silently target whatever
    workspace happens to sit above the cwd. An explicit `start` still wins,
    since the caller named it.

    start: where to begin walking, defaulting to the cwd.
    """
    if start is None and (pinned := os.environ.get(_ROOT_VARIABLE)):
        home = Path(pinned).resolve()
        if not _is_rooted(home):
            raise FileNotFoundError(
                f"{_ROOT_VARIABLE}={pinned} has no {Naming.CONFIG} with a [workspace] table"
            )
        return home
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if _is_rooted(candidate):
            return candidate
    raise FileNotFoundError(f"no {Naming.CONFIG} with a [workspace] table above {here}")

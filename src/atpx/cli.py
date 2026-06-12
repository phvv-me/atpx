import json
import sys

from cyclopts import App

from . import NAME
from .certificate import Certificate
from .workspace import Workspace, workspace


def verbatim(name: str) -> str:
    """Keep command names spelled exactly like the verbs, `cross_check` keeps its underscore."""
    return name


def display(result: object) -> None:
    """Print one verb result at the CLI boundary, exactly once.

    A certificate prints as its canonical JSON, a markdown verb (`brief`,
    `strategies`, `index`, ...) prints its text as-is, and plain data
    (`status`, `graph`, `checks`) prints as indented JSON, so every command
    is pipeable. Help and version produce no result and print nothing here.

    result: the value the verb returned, or None when no verb ran.
    """
    if result is None:
        return
    if isinstance(result, Certificate):
        print(result.model_dump_json(indent=2))
    elif isinstance(result, str):
        print(result)
    else:
        print(json.dumps(result, indent=2))


def build(space: Workspace) -> App:
    """Wire the workspace verbs into the cyclopts app, sync and async alike.

    The verbs register as bound methods, so the CLI surface is exactly the
    Python API: cyclopts owns the event loop and runs an async verb to
    completion, and `display` prints whatever comes back at the boundary.
    """
    app = App(
        name=NAME,
        help="Agentic mathematics workbench: every result is a certificate.",
        name_transform=verbatim,
        result_action=display,
    )
    app.command(space.check)
    app.command(space.checks)
    app.command(space.verify)
    app.command(space.brief)
    app.command(space.judge_brief)
    app.command(space.status)
    app.command(space.graph)
    app.command(space.recall)
    app.command(space.connect)
    app.command(space.strategies)
    app.command(space.lean_candidates)
    app.command(space.log)
    app.command(space.index)
    app.command(space.compute)
    app.command(space.prove)
    app.command(space.cross_check)
    return app


def main() -> None:
    """Open the workspace at the cwd and run one verb under the package name."""
    build(workspace())(sys.argv[1:])


if __name__ == "__main__":
    main()

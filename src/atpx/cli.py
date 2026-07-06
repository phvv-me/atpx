import json
import sys

from cyclopts import App

from . import NAME
from .certificate import Certificate
from .workspace import Workspace, workspace

# The verbs raise these with a message already written for a human, an unknown
# engine or slug, a missing claim or node, a forbidden role transition, a
# down search source. Catching exactly this tuple at the entry point turns each
# into one clean error line, while a genuine programming fault (a TypeError, an
# AttributeError) still surfaces its full traceback for debugging.
EXPECTED = (LookupError, ValueError, FileNotFoundError, RuntimeError, PermissionError)


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
    app.command(space.run)
    app.command(space.check)
    app.command(space.checks)
    app.command(space.verify)
    app.command(space.brief)
    app.command(space.judge_brief)
    app.command(space.status)
    app.command(space.graph)
    app.command(space.doctor)
    app.command(space.settle)
    app.command(space.lean)
    app.command(space.fit)
    app.command(space.recall)
    app.command(space.log)
    app.command(space.index)
    return app


def main() -> None:
    """Open the workspace at the cwd and run one verb under the package name.

    A verb's own domain error (unknown engine, missing slug, forbidden
    transition) prints as one `error:` line and exits nonzero, so the user
    reads the message the verb wrote rather than a Python traceback.
    """
    try:
        build(workspace())(sys.argv[1:])
    except EXPECTED as error:
        # KeyError stringifies its message in quotes, so read its raw arg to
        # keep the line the verb wrote ("demo has no claim 'ghost'") readable.
        message = error.args[0] if isinstance(error, KeyError) and error.args else error
        print(f"error: {message}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()

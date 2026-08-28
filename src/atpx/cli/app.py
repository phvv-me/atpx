import json
import sys
from pathlib import Path
from typing import Annotated, cast

from cyclopts import App, Parameter
from pydantic import JsonValue

from .. import Certificate, Workspace
from ..support.naming import Naming

# One clean `error:` line for the failures a verb writes for a human, a full
# traceback for genuine programming faults.
_EXPECTED = (
    LookupError,
    ValueError,
    FileNotFoundError,
    FileExistsError,
    RuntimeError,
    PermissionError,
)


def build(space: Workspace) -> App:
    """Wire the workspace verbs into the cyclopts app, sync and async alike.

    The verbs register as bound methods, so the CLI surface is exactly the
    Python API: cyclopts owns the event loop and runs an async verb to
    completion, and `reported` prints whatever comes back at the boundary.

    Nothing here opens the workspace. `space` resolves its root the first time a verb
    reaches for it, so `--help` and `--version` answer from any directory at all, and the
    `--project` pin the meta launcher accepts is still free to redirect it.
    """
    app = App(
        name=Naming.NAME,
        help="Agentic mathematics workbench: every result is a certificate.",
        name_transform=_verbatim,
        result_action=reported,
    )
    verbs = (
        space.run,
        space.ball,
        space.smt,
        space.lab,
        space.hunt,
        space.open,
        space.check,
        space.checks,
        space.verify,
        space.brief,
        space.judge_brief,
        space.status,
        space.graph,
        space.doctor,
        space.settle,
        space.prove,
        space.refute,
        space.lean,
        space.fit,
        space.recall,
        space.log,
        space.note,
        space.rule,
        space.design,
        space.adopt,
        space.index,
    )
    for verb in verbs:
        app.command(verb)

    @app.meta.default
    def launcher(
        *tokens: Annotated[str, Parameter(show=False, allow_leading_hyphen=True)],
        project: Path | None = None,
    ) -> Certificate | JsonValue:
        """Run one verb against one workspace.

        The verb's own result is handed straight back, since a nested app invocation
        leaves printing and the exit code to whichever app was entered from the shell.

        project: the workspace to act on, its root or any directory inside it, discovered
            from `ATPX_ROOT` or the current directory when omitted. The flag is what lets
            a verb reach a nested workspace from a tool that normalizes the working
            directory to the top of a monorepo before running anything.
        """
        space.given = project or space.given
        return cast("Certificate | JsonValue", app(tokens))

    return app


def display(result: Certificate | JsonValue) -> None:
    """Print one verb result at the CLI boundary, exactly once.

    A certificate prints as its canonical JSON, a markdown verb (`brief`,
    `index`, ...) prints its text as-is, and plain data (`status`, `graph`,
    `checks`) prints as indented JSON, so every command is pipeable. Help and
    version produce no result and print nothing here.

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


def reported(result: Certificate | JsonValue) -> None:
    """Print one verb result and let a failed certificate decide the exit code.

    The shell learns what the certificate already recorded, so `doctor`, `verify`, `ball`,
    `smt`, and `lab` gate a pipeline without anyone parsing their JSON. `hunt` keeps its
    documented inversion, where a clean exit means a counterexample was found.

    result: the value the verb returned, or None when no verb ran.
    """
    display(result)
    if isinstance(result, Certificate) and not result.ok:
        raise SystemExit(result.exit_status)


def main() -> None:
    """Run one verb under the package name, against the pinned or discovered workspace.

    A verb's own domain error (unknown engine, missing slug, forbidden
    transition) prints as one `error:` line and exits nonzero, so the user
    reads the message the verb wrote rather than a Python traceback.
    """
    try:
        build(Workspace()).meta(sys.argv[1:])
    except _EXPECTED as error:
        raise _complaint(error) from error


def _complaint(error: Exception) -> SystemExit:
    """One `error:` line on stderr and a nonzero exit for a verb's domain failure.

    KeyError stringifies its message in quotes, so its raw arg keeps the line
    the verb wrote (`demo has no claim 'ghost'`) readable.

    error: the domain error a verb raised.
    """
    message = error.args[0] if isinstance(error, KeyError) and error.args else error
    print(f"error: {message}", file=sys.stderr)
    return SystemExit(1)


def _verbatim(name: str) -> str:
    """Keep command names spelled exactly like the verbs, `judge_brief` keeps its underscore."""
    return name

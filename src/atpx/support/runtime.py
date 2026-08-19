import asyncio
from collections.abc import Coroutine


def drive[T](coroutine: Coroutine[None, None, T]) -> T:
    """Run one async verb to completion from synchronous code.

    The one event-loop boundary the package owns, under `Workspace.sync` and
    the compute-path `SearchEngine.execute`. The CLI never needs it, cyclopts
    owns the event loop there, and code already inside a running loop should
    await the verb directly, which this refuses with a clear error instead of
    asyncio's opaque nested-loop failure.

    coroutine: the async verb invocation to run.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _completed(coroutine)
    coroutine.close()
    raise RuntimeError(
        "this synchronous verb cannot run inside an active event loop, "
        "await the async verb directly instead"
    )


def _completed[T](coroutine: Coroutine[None, None, T]) -> T:
    """One fresh event loop for one coroutine, closed once it finishes."""
    with asyncio.Runner() as runner:
        return runner.run(coroutine)

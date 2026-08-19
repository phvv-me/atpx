from collections.abc import Callable, Coroutine

from atpx.engines import SearchEngine

from .reply import reply


def fetcher(engine_name: str) -> Callable[[SearchEngine, str], Coroutine[None, None, str]]:
    """An async fetch double replying with one canned hit."""

    async def fetch(engine: SearchEngine, payload: str) -> str:
        return reply(engine_name)

    return fetch

import asyncio
import json
from collections.abc import Sequence

from pydantic import JsonValue

from .engines import (
    Capability,
    Engine,
    EngineUnavailableError,
    SearchEngine,
    SearchError,
    UnsupportedOperationError,
)


async def fanned(
    query: str, names: Sequence[str] | None
) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    """Federated read-only search: (hits, errors) per source, one query fanned out at once.

    Sources come from the engine registry, by name or every search-capable
    one, and a named engine without the search capability is refused before
    any request starts. A `TaskGroup` rather than a bare gather: an
    unexpected fault in one source, or a ctrl-c reaching the loop, cancels
    the sibling requests and waits for them instead of abandoning
    half-finished connections.

    query: the search text every source receives.
    names: engine names to ask, defaulting to every search engine.
    """
    classes = (
        [Engine.find(name) for name in names] if names else Engine.supporting(Capability.SEARCH)
    )
    instances: list[SearchEngine] = []
    for engine in classes:
        if not issubclass(engine, SearchEngine):
            raise UnsupportedOperationError(
                f"{engine.name} only does {engine.capability.value}, not {Capability.SEARCH.value}"
            )
        instances.append(engine())

    async def attempted(instance: SearchEngine) -> tuple[JsonValue, str | None]:
        try:
            return json.loads(await instance.search(query)), None
        except (SearchError, EngineUnavailableError) as error:
            return None, str(error)

    async with asyncio.TaskGroup() as group:
        tasks = [(one.name, group.create_task(attempted(one))) for one in instances]
    hits: dict[str, JsonValue] = {}
    errors: dict[str, JsonValue] = {}
    for name, task in tasks:
        found, error = task.result()
        if error is None:
            hits[name] = found
        else:
            errors[name] = error
    return hits, errors

import asyncio
import json
from pathlib import Path

from pydantic import JsonValue

from .engines import (
    Capability,
    Engine,
    EngineUnavailableError,
    SearchEngine,
    SearchError,
    UnsupportedOperationError,
    VaultEngine,
)


class Recall:
    """Federated read-only search: one query fanned out to every source at once."""

    def __init__(self, root: Path) -> None:
        """root: the workspace root the vault source runs chefe from."""
        self.root = root

    async def fanned(
        self, query: str, names: list[str] | None
    ) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
        """(hits, errors) per source, gathered under structured cancellation.

        A `TaskGroup` rather than a bare gather: an unexpected fault in one
        source, or a ctrl-c reaching the loop, cancels the sibling requests
        and waits for them instead of abandoning half-finished connections.

        query: the search text every source receives.
        names: engine names to ask, defaulting to every search engine.
        """
        instances = [self.source(engine) for engine in self.selected(names)]
        async with asyncio.TaskGroup() as group:
            tasks = [
                (one.name, group.create_task(self.attempted(one, query))) for one in instances
            ]
        hits: dict[str, JsonValue] = {}
        errors: dict[str, JsonValue] = {}
        for name, task in tasks:
            found, error = task.result()
            if error is None:
                hits[name] = found
            else:
                errors[name] = error
        return hits, errors

    def selected(self, names: list[str] | None) -> list[type[Engine]]:
        """The engine classes to ask, by name or every search-capable one."""
        if names:
            return [Engine.find(name) for name in names]
        return Engine.supporting(Capability.SEARCH)

    def source(self, engine: type[Engine]) -> SearchEngine:
        """One ready search source, refusing engines without the search capability.

        engine: the registered engine class to instantiate.
        """
        if not issubclass(engine, SearchEngine):
            raise UnsupportedOperationError(
                f"{engine.name} only does {engine.capability.value}, not {Capability.SEARCH.value}"
            )
        return VaultEngine(self.root) if engine is VaultEngine else engine()

    async def attempted(self, instance: SearchEngine, query: str) -> tuple[JsonValue, str | None]:
        """(hits, None) from one source, or (None, error) when it is down or unreadable."""
        try:
            return json.loads(await instance.search(query)), None
        except (SearchError, EngineUnavailableError) as error:
            return None, str(error)

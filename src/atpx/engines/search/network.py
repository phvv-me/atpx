import json
import xml.etree.ElementTree as ElementTree
from abc import ABC, abstractmethod
from typing import ClassVar

import httpx

from .engine import Hit, SearchEngine
from .exceptions import SearchError

_TIMEOUT = 10.0
_LIMIT = 10


class NetworkSearchEngine(SearchEngine, ABC):
    """Shared async HTTP plumbing for the read-only web search sources.

    Abstract, so it never enrolls in the registry itself. Availability is EAFP:
    these engines always report available and surface network or shape failures
    at run time as `SearchError`, which `recall` turns into a nonzero
    certificate. A source may declare `empty_statuses`, HTTP codes its API uses
    to say "no results", which come back as zero hits rather than errors, while
    timeouts, connection failures, and 5xx stay genuine errors.
    """

    LIMIT: ClassVar[int] = _LIMIT

    empty_statuses: ClassVar[set[int]] = set()

    def available(self) -> bool:
        """Always true; reachability is settled by the request itself."""
        return True

    @abstractmethod
    def endpoint(self, query: str) -> str:
        """The full request URL for a query."""

    async def fetch(self, payload: str) -> str:
        """Fetch and shape one search, returning the hits as a JSON array string."""
        try:
            return await self.__shaped(payload)
        except (httpx.HTTPError, ValueError, KeyError, ElementTree.ParseError) as error:
            raise SearchError(f"{self.name}: {error}") from error

    @abstractmethod
    def hits(self, response: httpx.Response) -> list[Hit]:
        """Shape a successful response into hit records."""

    async def __shaped(self, payload: str) -> str:
        """One GET against the source, shaped to at most `LIMIT` hits."""
        async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(self.endpoint(payload))
        if response.status_code in self.empty_statuses:
            return json.dumps([])
        response.raise_for_status()
        return json.dumps(self.hits(response)[: self.LIMIT])

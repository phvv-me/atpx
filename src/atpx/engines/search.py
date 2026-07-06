import asyncio
import json
import shutil
import xml.etree.ElementTree as ElementTree
from abc import ABC, abstractmethod
from importlib.metadata import version as package_version
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote

import httpx

from .. import NAME
from ..runtime import drive
from .base import Capability, Engine

TIMEOUT = 10.0
LIMIT = 10
ATOM = {"atom": "http://www.w3.org/2005/Atom"}
Hit = dict[str, str | float]


class SearchError(RuntimeError):
    """Raised when a search source fails or returns a response atpx cannot read."""


class SearchEngine(Engine, ABC):
    """The I/O bound side of the registry, async sources under the sync Engine surface.

    A search source's real implementation is the async `fetch`. The `recall`
    verb awaits `search`, the guarded entry, on every source inside one event
    loop, while the inherited sync `Engine.run` path keeps working through
    `execute`, which drives `fetch` on a fresh loop. Compute engines never
    see any of this and the `Engine` contract stays synchronous. Abstract, so
    it never enrolls in the registry itself.
    """

    capability: ClassVar[Capability] = Capability.SEARCH

    def version(self) -> str:
        """This tool's own version, since it shapes the hits."""
        return package_version(NAME)

    @abstractmethod
    async def fetch(self, payload: str) -> str:
        """Run one search asynchronously, returning the hits as a JSON array string."""

    async def search(self, payload: str) -> str:
        """Guarded async entry, refusing hosts where this source is unavailable."""
        self.ensure_available()
        return await self.fetch(payload)

    def execute(self, payload: str) -> str:
        """Sync facade over `fetch`, keeping the registry contract uniform."""
        return drive(self.fetch(payload))


class VaultEngine(SearchEngine):
    """Lexical search over the Zettelkasten through qmd inside the chefe env.

    Runs `chefe run qmd -- search -c zettel --json` from the workspace root as
    an asyncio subprocess, the no-LLM BM25 surface, so recall never waits on a
    local model download.
    """

    name = "vault"

    def __init__(self, cwd: Path | None = None) -> None:
        """cwd: where chefe runs from, defaulting to the current directory."""
        self.cwd = cwd or Path.cwd()

    def available(self) -> bool:
        """Whether the chefe binary is on PATH."""
        return shutil.which("chefe") is not None

    def resolved(self) -> str:
        """The chefe binary's current PATH location, honoring PATH changes at call time."""
        return shutil.which("chefe") or "chefe"

    async def fetch(self, payload: str) -> str:
        """Search the zettel collection, returning the hits as a JSON array string."""
        argv = ["run", "qmd", "--", "search", "-c", "zettel", "--json", payload]
        process = await asyncio.create_subprocess_exec(
            self.resolved(),
            *argv,
            cwd=self.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise SearchError(
                f"{self.name}: qmd exited {process.returncode}: {stderr.decode().strip()[-500:]}"
            )
        try:
            entries = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise SearchError(f"{self.name}: qmd printed no JSON: {error}") from error
        hits: list[Hit] = [
            {
                "id": entry["file"],
                "title": entry["title"],
                "score": entry["score"],
                "snippet": entry["snippet"],
            }
            for entry in entries[:LIMIT]
        ]
        return json.dumps(hits)


class NetworkSearchEngine(SearchEngine, ABC):
    """Shared async HTTP plumbing for the read-only web search sources.

    Abstract, so it never enrolls in the registry itself. Availability is EAFP:
    these engines always report available and surface network or shape failures
    at run time as `SearchError`, which `recall` turns into a nonzero
    certificate. A source may declare `empty_statuses`, HTTP codes its API uses
    to say "no results", which come back as zero hits rather than errors, while
    timeouts, connection failures, and 5xx stay genuine errors.
    """

    empty_statuses: ClassVar[frozenset[int]] = frozenset()

    def available(self) -> bool:
        """Always true; reachability is settled by the request itself."""
        return True

    @abstractmethod
    def endpoint(self, query: str) -> str:
        """The full request URL for a query."""

    @abstractmethod
    def hits(self, response: httpx.Response) -> list[Hit]:
        """Shape a successful response into hit records."""

    async def fetch(self, payload: str) -> str:
        """Fetch and shape one search, returning the hits as a JSON array string."""
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
                response = await client.get(self.endpoint(payload))
            if response.status_code in self.empty_statuses:
                return json.dumps([])
            response.raise_for_status()
            return json.dumps(self.hits(response)[:LIMIT])
        except (httpx.HTTPError, ValueError, KeyError, ElementTree.ParseError) as error:
            raise SearchError(f"{self.name}: {error}") from error


class OeisEngine(NetworkSearchEngine):
    """Integer sequence lookup through the OEIS JSON search API."""

    name = "oeis"

    def endpoint(self, query: str) -> str:
        """OEIS search URL; comma-separated terms match sequences by their values."""
        return f"https://oeis.org/search?fmt=json&q={quote(query)}"

    def hits(self, response: httpx.Response) -> list[Hit]:
        """One hit per sequence: A-number, name, and its OEIS page."""
        body = response.json()
        results = body.get("results") if isinstance(body, dict) else body
        return [
            {
                "id": f"A{entry['number']:06d}",
                "title": entry["name"],
                "url": f"https://oeis.org/A{entry['number']:06d}",
            }
            for entry in results or []
        ]


class LoogleEngine(NetworkSearchEngine):
    """Mathlib declaration search through the loogle.lean-lang.org JSON API."""

    name = "loogle"

    def endpoint(self, query: str) -> str:
        """Loogle JSON URL; the query is a Lean pattern such as `Real.sqrt _ * _`."""
        return f"https://loogle.lean-lang.org/json?q={quote(query)}"

    def hits(self, response: httpx.Response) -> list[Hit]:
        """One hit per declaration: name, type signature, and defining module.

        Loogle only understands Lean identifiers and patterns, so its `error`
        field on a query it cannot parse ("Unknown identifier ...") means the
        query matches nothing, zero hits rather than a failed recall.
        """
        body = response.json()
        if "error" in body:
            return []
        return [
            {"id": entry["name"], "title": entry["type"], "module": entry["module"]}
            for entry in body.get("hits") or []
        ]


class ArxivEngine(NetworkSearchEngine):
    """Preprint search through the arXiv Atom export API."""

    name = "arxiv"

    def endpoint(self, query: str) -> str:
        """ArXiv export URL searching all fields as a phrase, capped at the hit limit."""
        phrase = quote(f'"{query}"')
        return f"https://export.arxiv.org/api/query?search_query=all:{phrase}&max_results={LIMIT}"

    def hits(self, response: httpx.Response) -> list[Hit]:
        """One hit per Atom entry: abstract URL and title."""
        feed = ElementTree.fromstring(response.text)
        return [
            {
                "id": entry.findtext("atom:id", "", ATOM).strip(),
                "title": " ".join(entry.findtext("atom:title", "", ATOM).split()),
            }
            for entry in feed.findall("atom:entry", ATOM)
        ]


class ZbmathEngine(NetworkSearchEngine):
    """Review search through the zbMATH Open REST API, keyless.

    The API answers a query with no matching documents as HTTP 404, so that
    status is zero hits, never an error.
    """

    name = "zbmath"
    empty_statuses: ClassVar[frozenset[int]] = frozenset({404})

    def endpoint(self, query: str) -> str:
        """ZbMATH Open document search URL."""
        return (
            "https://api.zbmath.org/v1/document/_search"
            f"?search_string={quote(query)}&results_per_page={LIMIT}"
        )

    def hits(self, response: httpx.Response) -> list[Hit]:
        """One hit per document: zbMATH identifier and title."""
        return [
            {
                "id": str(entry["zbmath_url"] or entry["identifier"]),
                "title": str(entry["title"]["title"]),
            }
            for entry in response.json()["result"]
        ]

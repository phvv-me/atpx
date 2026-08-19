import xml.etree.ElementTree as ElementTree
from urllib.parse import quote

import httpx

from ..engine import Hit
from ..network import NetworkSearchEngine

_ATOM = {"atom": "http://www.w3.org/2005/Atom"}


class ArxivEngine(NetworkSearchEngine):
    """Preprint search through the arXiv Atom export API."""

    name = "arxiv"
    precedence = 40

    def endpoint(self, query: str) -> str:
        """ArXiv export URL searching all fields as a phrase, capped at the hit limit."""
        phrase = quote(f'"{query}"')
        return (
            "https://export.arxiv.org/api/query"
            f"?search_query=all:{phrase}&max_results={self.LIMIT}"
        )

    def hits(self, response: httpx.Response) -> list[Hit]:
        """One hit per Atom entry: abstract URL and title."""
        feed = ElementTree.fromstring(response.text)
        return [
            {
                "id": entry.findtext("atom:id", "", _ATOM).strip(),
                "title": " ".join(entry.findtext("atom:title", "", _ATOM).split()),
            }
            for entry in feed.findall("atom:entry", _ATOM)
        ]

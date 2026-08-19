from typing import ClassVar
from urllib.parse import quote

import httpx

from ..engine import Hit
from ..network import NetworkSearchEngine


class ZbmathEngine(NetworkSearchEngine):
    """Review search through the zbMATH Open REST API, keyless.

    The API answers a query with no matching documents as HTTP 404, so that
    status is zero hits, never an error.
    """

    name = "zbmath"
    precedence = 50
    empty_statuses: ClassVar[set[int]] = {404}

    def endpoint(self, query: str) -> str:
        """ZbMATH Open document search URL."""
        return (
            "https://api.zbmath.org/v1/document/_search"
            f"?search_string={quote(query)}&results_per_page={self.LIMIT}"
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

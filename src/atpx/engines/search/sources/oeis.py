from urllib.parse import quote

import httpx

from ..engine import Hit
from ..network import NetworkSearchEngine


class OeisEngine(NetworkSearchEngine):
    """Integer sequence lookup through the OEIS JSON search API."""

    name = "oeis"
    precedence = 20

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

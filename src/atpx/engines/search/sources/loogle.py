from urllib.parse import quote

import httpx

from ..engine import Hit
from ..network import NetworkSearchEngine


class LoogleEngine(NetworkSearchEngine):
    """Mathlib declaration search through the loogle.lean-lang.org JSON API."""

    name = "loogle"
    precedence = 30

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

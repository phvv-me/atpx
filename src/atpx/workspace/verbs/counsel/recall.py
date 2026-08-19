from collections.abc import Sequence
from importlib.metadata import version as package_version

from ....core.certificate import Certificate
from ....recalling import fanned
from ....support.naming import Naming
from ...state import FoundationState


class RecallVerbs(FoundationState):
    """Federated read-only search, one certificate listing the hits per source."""

    async def recall(self, query: str, sources: Sequence[str] | None = None) -> Certificate:
        """Federated read-only search, one certificate listing the hits per source.

        query: the search text every source receives.
        sources: engine names to ask, defaulting to every search engine.
        """
        hits, errors = await fanned(query, sources)
        return Certificate.stamp(
            claim=f"recall {query}",
            result={"hits": hits, "errors": errors},
            engine=Naming.NAME,
            engine_version=package_version(Naming.NAME),
            exit_status=0 if not errors else 1,
            root=self.root,
        )

from pathlib import Path
from typing import Annotated, Protocol

from ...core.certificate import Certificate
from ...graph.store import NodeStore


class Workbench(Protocol):
    """The slice of the workspace counsel drives: the paths, the nodes, the run primitive.

    Read-only by declaration, since counsel only ever reads where the workspace is and
    never moves it, and a settable member here would refuse any provider that resolves
    its paths lazily.
    """

    @property
    def blueprints(self) -> Path: ...

    @property
    def nodes(self) -> NodeStore: ...

    @property
    def root(self) -> Path: ...

    async def run(
        self,
        slug: Annotated[str, "the blueprint directory name"],
        claim: str,
        *argv: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate: ...

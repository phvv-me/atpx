from collections.abc import Sequence
from typing import TYPE_CHECKING

from ...core.certificate import Certificate
from ...support.runtime import drive
from ..foundation import Slug

if TYPE_CHECKING:
    from ..verbs.facade import Workspace


class SyncVerbs:
    """The async workspace verbs as plain blocking calls, for one-liner scripts."""

    def __init__(self, verbs: Workspace) -> None:
        """verbs: the workspace whose async verbs this facade blocks on."""
        self.verbs = verbs

    def ball(
        self,
        slug: Slug,
        claim: str,
        *argv: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Blocking `Workspace.ball`, one ball-gated run to one certificate."""
        return drive(self.verbs.ball(slug, claim, *argv, seed=seed, timeout=timeout))

    def check(
        self, slug: Slug, claim: str, *, seed: int | None = None, background: bool = False
    ) -> Certificate:
        """Blocking `Workspace.check`, one claim run stamped and persisted."""
        return drive(self.verbs.check(slug, claim, seed=seed, background=background))

    def hunt(
        self,
        slug: Slug,
        claim: str,
        *argv: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Blocking `Workspace.hunt`, one counterexample search to one certificate."""
        return drive(self.verbs.hunt(slug, claim, *argv, seed=seed, timeout=timeout))

    def lab(
        self,
        slug: Slug,
        claim: str,
        *argv: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Blocking `Workspace.lab`, one receipt-gated study run to one certificate."""
        return drive(self.verbs.lab(slug, claim, *argv, seed=seed, timeout=timeout))

    def lean(
        self, slug: Slug, target: str | None = None, timeout: float | None = 3600
    ) -> Certificate:
        """Blocking `Workspace.lean`, one build ingested to one certificate."""
        return drive(self.verbs.lean(slug, target, timeout))

    def recall(self, query: str, sources: Sequence[str] | None = None) -> Certificate:
        """Blocking `Workspace.recall`, the federated search awaited to one certificate."""
        return drive(self.verbs.recall(query, sources))

    def run(
        self,
        slug: Slug,
        claim: str,
        *argv: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Blocking `Workspace.run`, capture-first execution to one certificate."""
        return drive(self.verbs.run(slug, claim, *argv, seed=seed, timeout=timeout))

    def smt(
        self,
        slug: Slug,
        claim: str,
        *argv: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Blocking `Workspace.smt`, one solver-gated run to one certificate."""
        return drive(self.verbs.smt(slug, claim, *argv, seed=seed, timeout=timeout))

    def verify(self, slug: str | None = None) -> Certificate:
        """Blocking `Workspace.verify`, the freshness sweep run to completion."""
        return drive(self.verbs.verify(slug))

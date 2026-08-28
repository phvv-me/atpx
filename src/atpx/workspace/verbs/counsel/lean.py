from ....core.certificate import Certificate
from ....core.evidence import EvidenceStore
from ....leaning import LeanAudit
from ...foundation import Slug
from ...state import FoundationState


class LeanVerbs(FoundationState):
    """Lean ingestion: run a build, audit it, stamp and persist the certificate."""

    async def lean(
        self, slug: Slug, target: str | None = None, timeout: float | None = 3600
    ) -> Certificate:
        """Ingest a Lean build as evidence: run it, audit it, stamp, persist.

        slug: the blueprint the certificate lands in, created when missing.
        target: the build target passed to the lean task, defaulting to none.
        timeout: hard wall-clock cap in seconds.
        """
        blueprint = self.register(slug, claim="lean")
        certificate = await LeanAudit(self.running, self.lean_task).certified(
            blueprint, target, timeout
        )
        EvidenceStore(blueprint.directory).append(certificate)
        return certificate

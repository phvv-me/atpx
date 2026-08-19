from pydantic import JsonValue

from ....counsel.prover import Prover
from ...foundation import Slug
from ...state import FoundationState


class ProveVerbs(FoundationState):
    """Summon the prover: cheap-model probes for one claim until a certificate lands."""

    def prove(
        self, slug: Slug, claim: str, *, spec: str, repairs: int = 2, timeout: float | None = None
    ) -> dict[str, JsonValue]:
        """Summon the prover: cheap-model probes for one claim until a certificate lands.

        Each probe executes through `run`, so a pass is a genuine stamped
        certificate in the evidence ledger, and the episode record appends to
        the blueprint's `attempts/` ledger.

        slug: the blueprint directory name, created when missing.
        claim: the claim name the certificate stamps.
        spec: path to the claim specification text, resolved cwd-first then root-relative.
        repairs: repair rounds allowed after the first probe.
        timeout: probe wall-clock cap in seconds matching the spec's stated
            budget, the measured 120s default when omitted.
        """
        text = self.filed(spec).read_text()
        attempt = Prover(self.lanes.prover).attempt(
            self, slug=slug, claim=claim, spec=text, repairs=repairs, timeout=timeout
        )
        return attempt.model_dump(mode="json")

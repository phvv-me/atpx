from collections.abc import Sequence
from pathlib import Path

from pydantic import JsonValue

from ..blueprint.manifest import Blueprint
from ..core.certificate import Certificate
from ..core.evidence import EvidenceStore
from .execution import Running


class FreshnessSweep:
    """One `verify` pass: re-run runnable claims, persist certificates, flag stale evidence."""

    def __init__(self, running: Running, blueprints: Path) -> None:
        """running: the claim execution seam.

        blueprints: the blueprints root directory.
        """
        self.running = running
        self.blueprints = blueprints

    def entry(self, certificate: Certificate | None, *, stale: bool) -> dict[str, JsonValue]:
        """One claim's report line: its state after the sweep and its stale flag."""
        state = "skipped" if certificate is None else "fresh" if certificate.ok else "failed"
        return {"state": state, "stale": stale}

    async def report(
        self, slugs: Sequence[str], revision: str
    ) -> tuple[dict[str, JsonValue], int]:
        """(per-blueprint claim states, failure count) for one sweep.

        Every runnable claim re-runs and its certificate persists; each claim
        reports `fresh`, `failed`, or `skipped` plus whether its prior evidence
        was stamped at another git revision.

        slugs: the blueprint names to sweep.
        revision: the workspace's current git revision, the staleness reference.
        """
        report: dict[str, JsonValue] = {}
        failures = 0
        for name in slugs:
            blueprint = Blueprint.load(self.blueprints / name)
            stale = stale_claims(blueprint, revision)
            runnable = [claim for claim, spec in blueprint.claims.items() if spec.is_runnable()]
            fresh = await self.running.swept(blueprint, runnable)
            store = EvidenceStore(blueprint.directory)
            for certificate in fresh.values():
                store.append(certificate)
            failures += sum(1 for certificate in fresh.values() if not certificate.ok)
            report[name] = {
                claim: self.entry(fresh.get(claim), stale=claim in stale)
                for claim in blueprint.claims
            }
        return report, failures


def stale_claims(blueprint: Blueprint, revision: str) -> set[str]:
    """Claims none of whose per-host latest certificates were stamped at `revision`.

    Hosts can disagree: one box re-ran after a commit while another still holds
    older evidence, and clocks across hosts are not comparable. So each host's
    ledger is judged by its own newest certificate per claim, and a claim only
    counts stale when no host's newest matches the current revision.

    blueprint: the loaded claim manifest.
    revision: the workspace's current git revision.
    """
    prefix = f"{blueprint.slug}/"
    owned = [
        (host, certificate)
        for host, ledger in EvidenceStore.ledgers(blueprint.directory).items()
        for certificate in ledger
        if certificate.claim.startswith(prefix)
    ]
    newest: dict[tuple[str, str], Certificate] = {}
    for host, certificate in owned:
        key = (host, certificate.claim.removeprefix(prefix))
        if key not in newest or certificate.timestamp > newest[key].timestamp:
            newest[key] = certificate
    fresh = {name for (_, name), certificate in newest.items() if certificate.git_rev == revision}
    return {key[1] for key in newest} - fresh

from collections.abc import Sequence
from importlib.metadata import version as package_version
from typing import Annotated

from cyclopts import Parameter

from ...background.checks import BackgroundChecks
from ...blueprint.manifest import Blueprint
from ...core import git_revision
from ...core.certificate import Certificate
from ...core.evidence import EvidenceStore
from ...rigor import Audit, BallAudit, LabAudit, SmtAudit, hunted
from ...rigor.lane import RigorLane
from ...running.sweep import FreshnessSweep
from ...support.console import announce
from ...support.naming import Naming
from ..foundation import Slug
from ..state import FoundationState


class CheckVerbs(FoundationState):
    """The capture-first execution verbs: run anything, gate on rigor, re-run, sweep."""

    async def ball(
        self,
        slug: Slug,
        claim: str,
        *argv: Annotated[str, Parameter(allow_leading_hyphen=True)],
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Run exactly like `run` but gate on rigorous ball enclosures, stamping rigor `ball`.

        The probe prints one `ball_certificate` JSON line per
        `atpx.is_ball_witness` call; the gate demands at least one line and
        every one verified, else rigor stays `sampled` and the exit is forced
        nonzero.

        slug: the blueprint directory name, created when missing.
        claim: the claim name, registered with this command when new.
        argv: the command tokens, separated with `--` when they carry flags.
        seed: RNG seed to record when the probe used one.
        timeout: hard wall-clock cap in seconds.
        """
        return await self.gated(
            slug, claim=claim, argv=list(argv), audit=BallAudit(), seed=seed, timeout=timeout
        )

    async def check(
        self, slug: Slug, claim: str, *, seed: int | None = None, background: bool = False
    ) -> Certificate:
        """Re-run one registered blueprint claim, stamp a certificate, persist it.

        A claim whose `requires` this host cannot meet is skipped gracefully:
        the returned certificate says so and nothing enters the evidence ledger,
        since a skip is not a run. With `background=True` the run detaches and
        the child persists the real certificate on completion.

        slug: the blueprint directory name under the blueprints root.
        claim: the claim name declared in the blueprint manifest.
        seed: RNG seed to record when the claim script used one.
        background: detach the run instead of waiting for it.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        if background:
            return BackgroundChecks(blueprint, self.root, self.launcher).submit(claim)
        spec = blueprint.claim(claim)
        if not spec.is_runnable():
            return self.skipped(slug, claim=claim, requirement=spec.requires or "")
        certificate = await self.running.attempted(blueprint, claim, seed=seed)
        EvidenceStore(blueprint.directory).append(certificate)
        return certificate

    def checks(self, slug: Slug) -> list[dict[str, str]]:
        """Background submissions for one blueprint, each pending or landed.

        slug: the blueprint directory name under the blueprints root.
        """
        blueprint = Blueprint.load(self.blueprints / slug)
        return BackgroundChecks(blueprint, self.root, self.launcher).listing()

    async def gated(
        self,
        slug: str,
        *,
        claim: str,
        argv: Sequence[str],
        audit: Audit,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """One rigor-gated run: register, execute, audit the full output, stamp, persist.

        slug: the blueprint directory name, created when missing.
        claim: the claim name, registered with `argv` when new.
        argv: the command tokens, empty to replay the registered command.
        audit: the stdout gate deciding whether the run earns its rigor.
        seed: RNG seed to record when the probe used one.
        timeout: hard wall-clock cap in seconds.
        """
        blueprint = self.register(slug, claim=claim, argv=argv)
        certificate = await RigorLane(self.running, audit).certified(
            blueprint, claim, seed=seed, timeout=timeout
        )
        EvidenceStore(blueprint.directory).append(certificate)
        return certificate

    async def hunt(
        self,
        slug: Slug,
        claim: str,
        *argv: Annotated[str, Parameter(allow_leading_hyphen=True)],
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Property-based counterexample search, the refuter convention, before any counsel.

        Exit 0 means the probe FOUND and shrunk a counterexample, printed in
        its output; nonzero means the property survived the search budget.
        The certificate stamps normally, rigor stays `sampled`, and one
        interpretation line prints either way. Hunt before summoning counsel
        refutation, since the search is free.

        slug: the blueprint directory name, created when missing.
        claim: the claim name, registered with this command when new.
        argv: the command tokens, separated with `--` when they carry flags.
        seed: RNG seed to record when the probe used one.
        timeout: hard wall-clock cap in seconds.
        """
        certificate = await self.run(slug, claim, *argv, seed=seed, timeout=timeout)
        announce(hunted(certificate))
        return certificate

    async def lab(
        self,
        slug: Slug,
        claim: str,
        *argv: Annotated[str, Parameter(allow_leading_hyphen=True)],
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Run exactly like `run` but gate on experiment trial receipts, stamping rigor `lab`.

        The verb for a claim whose verification is an experiment rather than a script. The
        command drives a study on whatever harness the workspace uses and prints one
        `trial_receipt` JSON line per trial; the gate demands at least one line and every
        trial through its declared gates. Each receipt lands in the certificate's witness
        list, so the evidence names the content-addressed `run_id` that produced it and
        re-verification is this same verb with no command at all, replaying what the
        manifest recorded.

        Rigor `lab` is evidence with an identity, not a proof, and the `validated` settle
        gate keeps refusing it exactly as it refuses `sampled`.

        slug: the blueprint directory name, created when missing.
        claim: the claim name, registered with this command when new.
        argv: the command tokens, separated with `--` when they carry flags, empty to
            replay the registered command.
        seed: RNG seed to record when the study used one.
        timeout: hard wall-clock cap in seconds.
        """
        return await self.gated(
            slug, claim=claim, argv=list(argv), audit=LabAudit(), seed=seed, timeout=timeout
        )

    def skipped(self, slug: str, *, claim: str, requirement: str) -> Certificate:
        """The unpersisted certificate for a claim this host cannot run."""
        return Certificate.stamp(
            claim=f"{slug}/{claim}",
            result={"skipped": True, "requires": requirement},
            engine=Naming.NAME,
            engine_version=package_version(Naming.NAME),
            root=self.root,
        )

    async def smt(
        self,
        slug: Slug,
        claim: str,
        *argv: Annotated[str, Parameter(allow_leading_hyphen=True)],
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Run exactly like `run` but gate on solver proofs, stamping rigor `smt`.

        The probe asserts the NEGATION of the claim in z3 and prints one
        `smt_certificate` JSON line per check; the gate demands at least one
        line and every result `unsat`. A `sat` result fails the gate, and the
        probe keeps the model in its output, a counterexample worth reading.

        slug: the blueprint directory name, created when missing.
        claim: the claim name, registered with this command when new.
        argv: the command tokens, separated with `--` when they carry flags.
        seed: RNG seed to record when the probe used one.
        timeout: hard wall-clock cap in seconds.
        """
        return await self.gated(
            slug, claim=claim, argv=list(argv), audit=SmtAudit(), seed=seed, timeout=timeout
        )

    async def verify(self, slug: str | None = None) -> Certificate:
        """Freshness sweep: re-run every claim this host can run and flag stale evidence.

        slug: one blueprint to sweep, defaulting to every blueprint with a manifest.
        """
        slugs = (
            [slug]
            if slug
            else sorted(p.parent.name for p in self.blueprints.glob(f"*/{Naming.CONFIG}"))
        )
        sweep = FreshnessSweep(self.running, self.blueprints)
        report, failures = await sweep.report(slugs, git_revision(self.root))
        return Certificate.stamp(
            claim=f"verify {slug}" if slug else "verify",
            result=report,
            engine=Naming.NAME,
            engine_version=package_version(Naming.NAME),
            exit_status=0 if not failures else 1,
            root=self.root,
        )

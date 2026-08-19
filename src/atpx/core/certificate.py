import platform
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue

from .provenance import Provenance


class Certificate(Provenance):
    """The one contract: every atpx operation returns one of these, never a naked result.

    `rigor` grades the evidence class of the result: `sampled` for ordinary
    numerical probes, `exact` for exact-arithmetic checks, `ball` for interval
    enclosures, `smt` for solver proofs, `lean` for kernel-checked builds. A
    plain string by design, so readers tolerate values outside that vocabulary
    the same way `doctor` tolerates an invented status.
    """

    claim: str
    result: JsonValue
    engine: str
    engine_version: str
    exit_status: int
    rigor: str = "sampled"

    def __str__(self) -> str:
        return self.model_dump_json(indent=2)

    @property
    def ok(self) -> bool:
        """Whether the operation exited cleanly."""
        return self.exit_status == 0

    @classmethod
    def stamp(
        cls,
        *,
        claim: str,
        result: JsonValue,
        engine: str,
        engine_version: str,
        exit_status: int = 0,
        seed: int | None = None,
        rigor: str = "sampled",
        root: Path | None = None,
    ) -> Certificate:
        """Build a certificate with provenance captured now, never reconstructed later.

        claim: claim text or id being certified.
        result: payload the operation produced.
        engine: name of the engine that ran.
        engine_version: its version string.
        exit_status: process or agreement exit code, zero means clean.
        seed: RNG seed when the operation used one.
        rigor: evidence class of the result, `sampled` unless an engine earned more.
        root: repository to stamp the git revision from, defaults to the cwd.
        """
        return cls(
            claim=claim,
            result=result,
            engine=engine,
            engine_version=engine_version,
            hostname=cls.short_hostname(),
            device=f"{platform.system()}-{platform.machine()}",
            seed=seed,
            git_rev=cls.git_revision(root or Path.cwd()),
            timestamp=datetime.now(UTC).isoformat(),
            exit_status=exit_status,
            rigor=rigor,
        )

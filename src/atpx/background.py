from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path
from subprocess import DEVNULL, STDOUT, Popen

from . import NAME
from .base import FrozenModel
from .blueprint import Blueprint
from .certificate import Certificate
from .evidence import EvidenceStore


class Submission(FrozenModel):
    """One detached claim run, recorded beside its log in the blueprint's `checks/` dir."""

    claim: str
    submitted: str
    pid: int


class BackgroundChecks:
    """Detached claim runs for one blueprint, their logs and submissions under `checks/`.

    `submit` spawns `chefe run <tool> check <slug> <claim>` in its own session
    with stdout streamed into the blueprint directory. The child stamps and
    persists the real certificate exactly as a foreground check does, so a
    submission has `landed` once the evidence ledgers hold a certificate for its
    claim stamped after submission time. Transport stays composition: a remote
    background check is lote running this same CLI on another host.
    """

    def __init__(self, blueprint: Blueprint, root: Path) -> None:
        """blueprint: the claim manifest the checks run against.

        root: the workspace root chefe runs from.
        """
        self.blueprint = blueprint
        self.root = root
        self.directory = blueprint.directory / "checks"

    def submit(self, claim: str) -> Certificate:
        """Detach one claim run, returning a submission certificate (never persisted).

        claim: the claim name declared in the blueprint manifest.
        """
        self.blueprint.claim(claim)
        submitted = datetime.now(UTC)
        stem = f"{claim}-{submitted.strftime('%Y%m%dT%H%M%S%f')}"
        self.directory.mkdir(parents=True, exist_ok=True)
        log = self.directory / f"{stem}.log"
        argv = ["chefe", "run", NAME, "check", self.blueprint.slug, claim]
        with log.open("w") as sink:
            process = Popen(
                argv,
                cwd=self.root,
                stdin=DEVNULL,
                stdout=sink,
                stderr=STDOUT,
                start_new_session=True,
            )
        record = Submission(claim=claim, submitted=submitted.isoformat(), pid=process.pid)
        (self.directory / f"{stem}.json").write_text(record.model_dump_json(indent=2) + "\n")
        return Certificate.stamp(
            claim=f"{self.blueprint.slug}/{claim}",
            result={"detached": True, "pid": process.pid, "log": str(log.relative_to(self.root))},
            engine=NAME,
            engine_version=package_version(NAME),
            root=self.root,
        )

    def listing(self) -> list[dict[str, str]]:
        """Every submission with its state, `landed` once a newer certificate exists."""
        ledgers = EvidenceStore.ledgers(self.blueprint.directory)
        certificates = [entry for ledger in ledgers.values() for entry in ledger]
        rows = []
        for path in sorted(self.directory.glob("*.json")):
            submission = Submission.model_validate_json(path.read_text())
            landed = any(
                entry.claim == f"{self.blueprint.slug}/{submission.claim}"
                and entry.timestamp >= submission.submitted
                for entry in certificates
            )
            rows.append(
                {
                    "claim": submission.claim,
                    "submitted": submission.submitted,
                    "state": "landed" if landed else "pending",
                }
            )
        return rows

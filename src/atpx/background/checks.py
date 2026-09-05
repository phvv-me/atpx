from collections.abc import Sequence
from importlib.metadata import version as package_version
from pathlib import Path
from shutil import which
from subprocess import DEVNULL, STDOUT, Popen

from ..blueprint.manifest import Blueprint
from ..core.certificate import Certificate
from ..core.evidence import EvidenceStore
from ..support.clock import compact, moment, stamp
from ..support.naming import Naming
from .submission import Submission


class BackgroundChecks:
    """Detached claim runs for one blueprint, their logs and submissions under `checks/`.

    `submit` spawns the workspace launcher's own `<tool> check <slug> <claim>` in its
    own session with stdout streamed into the blueprint directory, the same launcher a
    foreground claim runs behind so a detached check lands in the same environment. The
    child stamps and persists the real certificate exactly as a foreground check does, so
    a submission has `landed` once the evidence ledgers hold a certificate for its claim
    stamped after submission time. Transport stays composition: a remote background check
    is the dispatcher running this same CLI on another host.
    """

    def __init__(self, blueprint: Blueprint, root: Path, launcher: Sequence[str] = ()) -> None:
        """blueprint: the claim manifest the checks run against.

        root: the workspace root the detached child runs from.
        launcher: the workspace's declared command prefix.
        """
        self.blueprint = blueprint
        self.root = root
        self.launcher = launcher
        self.directory = blueprint.directory / "checks"

    def listing(self) -> list[dict[str, str]]:
        """Every submission with its state, `landed` once a newer certificate exists."""
        ledgers = EvidenceStore.ledgers(self.blueprint.directory)
        certificates = [entry for ledger in ledgers.values() for entry in ledger]
        rows = []
        for path in sorted(self.directory.glob("*.json")):
            submission = Submission.model_validate_json(path.read_text(encoding="utf-8"))
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

    def submit(self, claim: str) -> Certificate:
        """Detach one claim run, returning a submission certificate (never persisted).

        claim: the claim name declared in the blueprint manifest.
        """
        self.blueprint.claim(claim)
        submitted = moment()
        stem = f"{claim}-{compact(submitted)}"
        self.directory.mkdir(parents=True, exist_ok=True)
        log = self.directory / f"{stem}.log"
        argv = [*self.launcher, Naming.NAME, "check", self.blueprint.slug, claim]
        argv[0] = which(argv[0]) or argv[0]
        with log.open("w", encoding="utf-8") as sink:
            process = Popen(
                argv,
                cwd=self.root,
                stdin=DEVNULL,
                stdout=sink,
                stderr=STDOUT,
                start_new_session=True,
            )
        record = Submission(claim=claim, submitted=stamp(submitted), pid=process.pid)
        (self.directory / f"{stem}.json").write_text(
            record.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        return Certificate.stamp(
            claim=f"{self.blueprint.slug}/{claim}",
            result={
                "detached": True,
                "pid": process.pid,
                "log": log.relative_to(self.root).as_posix(),
            },
            engine=Naming.NAME,
            engine_version=package_version(Naming.NAME),
            root=self.root,
        )

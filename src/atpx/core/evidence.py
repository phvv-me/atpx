import json
from pathlib import Path

from filelock import FileLock

from .certificate import Certificate
from .exceptions import EvidenceError
from .provenance import Provenance

_LOCK_TIMEOUT = 10.0


class EvidenceStore:
    """Per-host append-only certificate ledger inside a blueprint directory.

    Each host owns exactly one file, `evidence/<hostname>.json`, and only ever appends
    to it, so two hosts can never clobber each other's provenance. A file lock guards
    the read-modify-write, since two processes on the same host (an overlapping
    `--background` run, say) can otherwise race and silently drop a certificate.
    """

    def __init__(self, directory: Path, hostname: str | None = None) -> None:
        """directory: the blueprint directory holding `evidence/`.

        hostname: owner of the ledger, defaults to this host.
        """
        self.hostname = hostname or Provenance.short_hostname()
        self.path = directory / "evidence" / f"{self.hostname}.json"

    @classmethod
    def ledgers(cls, directory: Path) -> dict[str, list[Certificate]]:
        """Every host's certificates under a blueprint directory, keyed by hostname.

        Tolerant by design: a file under `evidence/` that is not a certificate
        ledger (agents park raw data artifacts there) is skipped here and
        reported by `strays` and `doctor`, never an exception.

        directory: the blueprint directory holding `evidence/`.
        """
        readings = {
            file.stem: cls(directory, hostname=file.stem).maybe_read()
            for file in sorted((directory / "evidence").glob("*.json"))
        }
        return {hostname: entries for hostname, entries in readings.items() if entries is not None}

    @classmethod
    def newest(cls, directory: Path, slug: str) -> dict[str, Certificate]:
        """The most recent certificate per claim of `slug`, folded over every host's ledger.

        The lint's view of a blueprint's evidence: what does the record currently say
        about each claim, whoever ran it last. `stale_claims` deliberately keeps its own
        per-host fold instead, since it compares revisions across machines whose clocks
        are not comparable, while a lint only ever asks for the latest word.

        directory: the blueprint directory holding `evidence/`.
        slug: the blueprint name every certificate prefixes its claim with.
        """
        prefix = f"{slug}/"
        owned = [
            (certificate.claim.removeprefix(prefix), certificate)
            for ledger in cls.ledgers(directory).values()
            for certificate in ledger
            if certificate.claim.startswith(prefix)
        ]
        return dict(sorted(owned, key=lambda pair: pair[1].timestamp))

    @classmethod
    def strays(cls, directory: Path) -> list[Path]:
        """Files under `evidence/` that are not certificate ledgers, for `doctor`.

        directory: the blueprint directory holding `evidence/`.
        """
        return [
            file
            for file in sorted((directory / "evidence").glob("*.json"))
            if cls(directory, hostname=file.stem).maybe_read() is None
        ]

    def append(self, certificate: Certificate) -> Path:
        """Append one certificate, refusing anything stamped by another host.

        Locked around the read-modify-write, so two processes racing to
        extend the same host's ledger can never clobber each other's certificate.

        certificate: the freshly stamped record to persist.
        """
        if certificate.hostname != self.hostname:
            raise EvidenceError(
                f"certificate from {certificate.hostname} cannot enter {self.hostname}'s ledger"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with FileLock(f"{self.path}.lock", timeout=_LOCK_TIMEOUT):
            existing = self.read()
            for prior in existing:
                if prior.hostname != self.hostname:
                    raise EvidenceError(
                        f"{self.path} holds foreign evidence from {prior.hostname}"
                    )
            records = [entry.model_dump() for entry in [*existing, certificate]]
            self.path.write_text(json.dumps(records, indent=2) + "\n")
        return self.path

    def maybe_read(self) -> list[Certificate] | None:
        """The ledger's certificates, or None when the file is not a ledger at all."""
        try:
            return self.read()
        except EvidenceError:
            return None

    def read(self) -> list[Certificate]:
        """All certificates recorded so far, oldest first.

        Raises `EvidenceError` when the file exists but is not a certificate
        ledger, so `append` can refuse to grow a data artifact while the
        tolerant readers skip it.
        """
        try:
            entries = json.loads(self.path.read_text())
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as error:
            raise EvidenceError(f"{self.path} is not a certificate ledger: {error}") from error
        try:
            return [Certificate.model_validate(entry) for entry in entries]
        except (TypeError, ValueError) as error:
            raise EvidenceError(f"{self.path} is not a certificate ledger") from error

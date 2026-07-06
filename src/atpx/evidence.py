import json
from pathlib import Path

from .certificate import Certificate, short_hostname


class EvidenceError(RuntimeError):
    """Raised when a write would break the one-file-per-host append-only discipline."""


class EvidenceStore:
    """Per-host append-only certificate ledger inside a blueprint directory.

    Each host owns exactly one file, `evidence/<hostname>.json`, and only ever appends
    to it, so two hosts can never clobber each other's provenance.
    """

    def __init__(self, directory: Path, hostname: str | None = None) -> None:
        """directory: the blueprint directory holding `evidence/`.

        hostname: owner of the ledger, defaults to this host.
        """
        self.hostname = hostname or short_hostname()
        self.path = directory / "evidence" / f"{self.hostname}.json"

    @classmethod
    def ledgers(cls, directory: Path) -> dict[str, list[Certificate]]:
        """Every host's certificates under a blueprint directory, keyed by hostname.

        Tolerant by design: a file under `evidence/` that is not a certificate
        ledger (agents park raw data artifacts there) is skipped here and
        reported by `strays` and `doctor`, never an exception.

        directory: the blueprint directory holding `evidence/`.
        """
        found = {}
        for file in sorted((directory / "evidence").glob("*.json")):
            try:
                found[file.stem] = cls(directory, hostname=file.stem).read()
            except EvidenceError:
                continue
        return found

    @classmethod
    def strays(cls, directory: Path) -> list[Path]:
        """Files under `evidence/` that are not certificate ledgers, for `doctor`.

        directory: the blueprint directory holding `evidence/`.
        """
        stray = []
        for file in sorted((directory / "evidence").glob("*.json")):
            try:
                cls(directory, hostname=file.stem).read()
            except EvidenceError:
                stray.append(file)
        return stray

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

    def append(self, certificate: Certificate) -> Path:
        """Append one certificate, refusing anything stamped by another host.

        certificate: the freshly stamped record to persist.
        """
        if certificate.hostname != self.hostname:
            raise EvidenceError(
                f"certificate from {certificate.hostname} cannot enter {self.hostname}'s ledger"
            )
        existing = self.read()
        for prior in existing:
            if prior.hostname != self.hostname:
                raise EvidenceError(f"{self.path} holds foreign evidence from {prior.hostname}")
        records = [entry.model_dump() for entry in [*existing, certificate]]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(records, indent=2) + "\n")
        return self.path

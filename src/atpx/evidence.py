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

        directory: the blueprint directory holding `evidence/`.
        """
        files = sorted((directory / "evidence").glob("*.json"))
        return {file.stem: cls(directory, hostname=file.stem).read() for file in files}

    def read(self) -> list[Certificate]:
        """All certificates recorded so far, oldest first."""
        try:
            entries = json.loads(self.path.read_text())
        except FileNotFoundError:
            return []
        return [Certificate.model_validate(entry) for entry in entries]

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

from functools import cached_property
from pathlib import Path
from typing import ClassVar

from pydantic import JsonValue

from .certificate import Certificate
from .exceptions import EvidenceError
from .provenance import Provenance
from .streaming import Stream


class EvidenceStore:
    """Per-host append-only certificate ledger inside a blueprint directory.

    Each host owns one stream, `evidence/<hostname>.ndjson`, holding one certificate
    per line, and a write only ever opens it for append. That is the whole point of
    the format: a killed process, a full disk, or a record whose stored output was
    truncated costs exactly the line it was writing, while every certificate around
    it still reads. A file lock guards the append, since two processes on the same
    host (an overlapping `--background` run, say) can otherwise interleave a line.

    The pre-stream format, one whole-file JSON array at `evidence/<hostname>.json`,
    is read and never rewritten. A ledger recorded before the migration keeps
    reading as one, its history stays byte for byte what was recorded, and the two
    formats fold into one chronological reading of the host.
    """

    ARRAY: ClassVar[str] = ".json"
    STREAM: ClassVar[str] = ".ndjson"

    def __init__(self, directory: Path, hostname: str | None = None) -> None:
        """directory: the blueprint directory holding `evidence/`.

        hostname: owner of the ledger, defaults to this host.
        """
        self.hostname = hostname or Provenance.short_hostname()
        self.path = directory / "evidence" / f"{self.hostname}{self.STREAM}"
        self.array = directory / "evidence" / f"{self.hostname}{self.ARRAY}"

    @cached_property
    def stream(self) -> Stream:
        """The append-only NDJSON half of this host's ledger."""
        return Stream(self.path)

    @classmethod
    def entries(cls, file: Path) -> list[Certificate]:
        """Every certificate one ledger file holds, torn records warned about and skipped.

        The reading rule both formats share: a record that does not decode, or decodes
        into something no stamp could have produced, is reported as a `TornLedger`
        warning naming exactly where it sits and then left out. Nothing here ever
        raises, so one bad record can never hide the ledger around it.

        file: a ledger file under a blueprint's `evidence/`.
        """
        return [
            certificate
            for where, record in cls.records(file)
            if (certificate := cls.__certificate(record, where)) is not None
        ]

    @classmethod
    def files(cls, directory: Path) -> list[Path]:
        """Every ledger-shaped file under a blueprint's `evidence/`, both formats, sorted.

        directory: the blueprint directory holding `evidence/`.
        """
        return sorted(
            file
            for file in (directory / "evidence").glob("*")
            if file.suffix in (cls.ARRAY, cls.STREAM)
        )

    @classmethod
    def hosts(cls, directory: Path) -> list[str]:
        """Every hostname holding a ledger file under a blueprint's `evidence/`, sorted.

        A host that already wrote both formats answers once, since the stream and the
        array it was migrated from are two halves of that host's one ledger.

        directory: the blueprint directory holding `evidence/`.
        """
        return sorted({file.stem for file in cls.files(directory)})

    @classmethod
    def ledgers(cls, directory: Path) -> dict[str, list[Certificate]]:
        """Every host's certificates under a blueprint directory, keyed by hostname.

        Tolerant by design: a file under `evidence/` that is not a certificate
        ledger (agents park raw data artifacts there) yields nothing here and
        is reported by `strays` and `doctor`, never an exception.

        directory: the blueprint directory holding `evidence/`.
        """
        readings = {host: cls(directory, hostname=host).read() for host in cls.hosts(directory)}
        return {hostname: entries for hostname, entries in readings.items() if entries}

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
    def records(cls, file: Path) -> list[tuple[str, JsonValue]]:
        """(where it sits, decoded record) for one ledger file, undecodable parts warned away.

        The stream is one record per line and reads through `Stream`; the array is one
        record per element and is decoded whole, since that format cannot be read any
        other way. So `where` is `<file>:<line>` for the first and `<file>[<position>]`
        for the second, which is the whole of what a reader needs to go and look at the
        damage.

        file: a ledger file under a blueprint's `evidence/`.
        """
        if file.suffix == cls.STREAM:
            return Stream(file).records
        array = cls.__array(file)
        return [(f"{file}[{position}]", record) for position, record in enumerate(array, start=1)]

    @classmethod
    def strays(cls, directory: Path) -> list[Path]:
        """Ledger-shaped files under `evidence/` holding no certificate at all, for `doctor`.

        A torn record never makes its ledger a stray, since the rest of the file still
        reads; only a file this store could not have written at all lands here.

        directory: the blueprint directory holding `evidence/`.
        """
        return [file for file in cls.files(directory) if not cls.entries(file)]

    def append(self, certificate: Certificate) -> Path:
        """Append one certificate as one line, refusing anything stamped by another host.

        One line, one open-for-append, no rewrite of anything already recorded, so a
        write that dies halfway can only ever damage its own record. Locked, since two
        processes racing to extend the same host's ledger can otherwise interleave.

        certificate: the freshly stamped record to persist.
        """
        if certificate.hostname != self.hostname:
            raise EvidenceError(
                f"certificate from {certificate.hostname} cannot enter {self.hostname}'s ledger"
            )
        with self.stream.guard:
            for prior in self.read():
                if prior.hostname != self.hostname:
                    raise EvidenceError(
                        f"{self.hostname}'s ledger holds foreign evidence from {prior.hostname}"
                    )
            return self.stream.append(certificate.model_dump_json())

    def read(self) -> list[Certificate]:
        """This host's certificates, the migrated array first and then the stream.

        Never raises for content: an unreadable record warns and drops out, so the
        ledger a lint, a gate, or `doctor` sees is always everything that is still
        legible rather than nothing at all.
        """
        return [
            certificate
            for file in (self.array, self.path)
            if file.exists()
            for certificate in self.entries(file)
        ]

    @staticmethod
    def __array(file: Path) -> list[JsonValue]:
        """The pre-migration array's elements, empty with a warning when it is not one."""
        decoded = Stream.decoded(file.read_bytes(), where=str(file))
        if isinstance(decoded, list):
            return decoded
        if decoded is not None:
            Stream.skipped(f"{file} is not a certificate array, skipping it")
        return []

    @staticmethod
    def __certificate(record: JsonValue, where: str) -> Certificate | None:
        """One decoded record as a certificate, None with a warning when it is not one."""
        try:
            return Certificate.model_validate(record)
        except ValueError:
            return Stream.skipped(f"{where} is not a certificate, skipping it")

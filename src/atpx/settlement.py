from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from patos import Registry

from .base import FrozenModel
from .briefing import JudgmentLedger
from .certificate import Certificate
from .evidence import EvidenceStore
from .roles import Status
from .zettel import LogEntry, Zettel


class SettleError(PermissionError):
    """Raised when a settling transition lacks the evidence artifact it requires."""


class Petition(FrozenModel):
    """One settle request: the journal message and the artifact references offered."""

    message: str = ""
    judgment: str | None = None
    counterexample: str | None = None
    lean: str | None = None


class Gate(Registry, ABC):
    """The evidence demand guarding one settling transition.

    A new gated status is a new subclass, never an edit here: declare the
    `status` it guards, return the journal reference from `granted` (raising
    `SettleError` when the petition falls short), and override `commit` when
    the transition leaves an artifact behind. Statuses no gate guards are
    free and fall through.
    """

    status: ClassVar[Status]

    @classmethod
    def of(cls, target: Status) -> Gate | None:
        """The gate guarding `target`, None for the free statuses."""
        guards = [gate for gate in cls.implementations() if gate.status is target]
        return guards[0]() if guards else None

    @abstractmethod
    def granted(self, node: Zettel, root: Path, petition: Petition) -> str:
        """The journal reference once the petition satisfies this gate."""

    def commit(self, node: Zettel, root: Path) -> None:
        """Post-transition artifact hook, a no-op unless a gate overrides it."""


class SketchGate(Gate):
    """`sketched` demands the recorded refuter ruling and snapshots the judged node."""

    status: ClassVar[Status] = Status.SKETCHED

    def granted(self, node: Zettel, root: Path, petition: Petition) -> str:
        """Demand a ruling file that exists root-relative or as given."""
        ruling = Path(petition.judgment) if petition.judgment else None
        found = ruling is not None and ((root / ruling).exists() or ruling.exists())
        if not found:
            raise SettleError("sketched requires --judgment pointing at the recorded ruling")
        return f"judgment {petition.judgment}"

    def commit(self, node: Zettel, root: Path) -> None:
        """Snapshot the node as judged right now, the diff base `judge_brief` reads."""
        if node.blueprint:
            JudgmentLedger(root / node.blueprint).record(node)


class RefuteGate(Gate):
    """`refuted` demands a persisted counterexample certificate in the node's ledgers."""

    status: ClassVar[Status] = Status.REFUTED

    def granted(self, node: Zettel, root: Path, petition: Petition) -> str:
        """Demand the counterexample certificate and name it in the journal."""
        witness = certified(node, root, petition.counterexample, "refuted")
        return f"counterexample {witness.claim}"


class VerifyGate(Gate):
    """`verified` demands a clean Lean build certificate, zero sorries and nothing flagged."""

    status: ClassVar[Status] = Status.VERIFIED

    def granted(self, node: Zettel, root: Path, petition: Petition) -> str:
        """Demand the Lean certificate, refuse dirty builds and risky axioms."""
        certificate = certified(node, root, petition.lean, "verified")
        audit = certificate.result if isinstance(certificate.result, dict) else {}
        if not certificate.ok or audit.get("sorries", 1):
            raise SettleError(f"{certificate.claim} is not a clean Lean build, cannot verify")
        if audit.get("flagged"):
            raise SettleError(
                f"{certificate.claim} leans on risky axioms {audit['flagged']}, cannot verify"
            )
        return f"lean {certificate.claim}"


class Settlement:
    """Moves node statuses behind the evidence gates, journaling every move."""

    def __init__(self, root: Path) -> None:
        """root: the workspace root the blueprint ledgers resolve against."""
        self.root = root

    def move(self, node: Zettel, target: Status, petition: Petition) -> str:
        """Demand the gate's artifact, journal the move, set the status, commit.

        node: the zettel whose status moves.
        target: the destination lifecycle status.
        petition: the message and artifact references offered.
        """
        gate = Gate.of(target)
        reference = gate.granted(node, self.root, petition) if gate else ""
        body = " ".join(part for part in (petition.message, reference) if part)
        entry = LogEntry.today(who="settle", tag=target.value, message=body)
        node.append_log(str(entry))
        node.set_status(target)
        if gate:
            gate.commit(node, self.root)
        return str(entry)


def certified(node: Zettel, root: Path, claim: str | None, gate: str) -> Certificate:
    """The persisted certificate named by `claim` in the node's blueprint ledgers.

    node: the zettel whose blueprint holds the evidence.
    root: the workspace root the blueprint path resolves against.
    claim: the certificate claim id to find.
    gate: the transition asking, named in the refusal message.
    """
    blueprint = node.blueprint
    if not claim or not blueprint:
        raise SettleError(
            f"{gate} requires a persisted certificate reference and a blueprint field"
        )
    for ledger in EvidenceStore.ledgers(root / blueprint).values():
        for certificate in ledger:
            if certificate.claim == claim or certificate.claim.endswith(f"/{claim}"):
                return certificate
    raise SettleError(f"no certificate {claim!r} found in {blueprint} ledgers")

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from patos import Registry

from ..core.certificate import Certificate
from ..core.evidence import EvidenceStore
from ..graph.node import Node
from ..graph.status import Status
from .exceptions import SettleError
from .petition import Petition


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

    def commit(self, node: Node, root: Path) -> None:
        """Post-transition artifact hook, a no-op unless a gate overrides it."""

    def demand(self, node: Node, claim: str | None) -> Certificate:
        """The persisted certificate named by `claim` in the node's blueprint ledgers.

        node: the node whose blueprint directory holds the evidence.
        claim: the certificate claim id to find, refused when empty or absent.
        """
        if not claim:
            raise SettleError(f"{self.status.value} requires a persisted certificate reference")
        for ledger in EvidenceStore.ledgers(node.directory).values():
            for certificate in ledger:
                if certificate.claim == claim or certificate.claim.endswith(f"/{claim}"):
                    return certificate
        raise SettleError(f"no certificate {claim!r} found in {node.name} ledgers")

    @abstractmethod
    def granted(self, node: Node, root: Path, petition: Petition) -> str:
        """The journal reference once the petition satisfies this gate."""

from collections.abc import Iterable
from functools import cached_property
from pathlib import Path

from pydantic import JsonValue

from ...blueprint.manifest import Blueprint
from ...core.certificate import Certificate
from ...core.evidence import EvidenceStore
from ...core.repository import Repository
from ...graph.node import Node
from ...graph.store import NodeStore
from ...support.naming import Naming


class ClaimLints:
    """The evidence lints: what each blueprint's certificates say against its claims."""

    def __init__(self, nodes: NodeStore, *, root: Path) -> None:
        """nodes: the blueprint node graph whose claims are linted.

        root: the workspace root whose repository dates the evidence.
        """
        self.nodes = nodes
        self.repository = Repository(root)

    def compiled(self) -> dict[str, JsonValue]:
        """This group's report slice, one key per lint."""
        return {
            "failing_claims": self.failing_claims(),
            "unevidenced_claims": self.unevidenced_claims(),
            "stale_claims": self.stale_claims(),
        }

    def failing_claims(self) -> dict[str, JsonValue]:
        """Claims whose newest certificate exited nonzero, per blueprint.

        Read literally, because a claim command is a check and a check that exits nonzero
        did not pass. The one place that reads the other way is `hunt`, whose refuter
        convention makes a clean exit the bad news, so a counterexample search belongs
        behind that verb rather than registered here as an ordinary claim.
        """
        return self.__grouped(
            (node, claim)
            for node, claim, certificate in self.__evidence
            if certificate is not None and not certificate.ok
        )

    def stale_claims(self) -> dict[str, JsonValue]:
        """Claims whose newest certificate predates the last change to their node, per blueprint.

        The lint that keeps a settled node honest: editing a statement without re-running
        its checks leaves evidence that certifies something the node no longer says.
        """
        return self.__grouped(
            (node, claim)
            for node, claim, certificate in self.__evidence
            if certificate is not None
            and self.repository.moved_since(certificate.git_rev, node.path)
        )

    def unevidenced_claims(self) -> dict[str, JsonValue]:
        """Declared claims no host has ever certified, per blueprint."""
        return self.__grouped(
            (node, claim) for node, claim, certificate in self.__evidence if certificate is None
        )

    @cached_property
    def __evidence(self) -> list[tuple[Node, str, Certificate | None]]:
        """Every declared claim of every node of record, paired with its newest certificate.

        The one walk the three evidence lints share, read once per report so a blueprint's
        manifest and its ledgers are not reopened per lint. Superseded stubs are left out:
        their claims are frozen history certified where they were run, so holding them to
        the freshness of a statement that has moved would report a repair nobody can make.
        """
        rows = []
        for node in self.nodes.canonical():
            if not (node.directory / Naming.CONFIG).exists():
                continue
            latest = EvidenceStore.newest(node.directory, node.name)
            claims = Blueprint.load(node.directory).claims
            rows += [(node, claim, latest.get(claim)) for claim in claims]
        return rows

    @staticmethod
    def __grouped(findings: Iterable[tuple[Node, str]]) -> dict[str, JsonValue]:
        """Claim findings collected under their blueprint name, each list sorted.

        findings: (node, claim) pairs one lint flagged.
        """
        report: dict[str, list[str]] = {}
        for node, claim in findings:
            report.setdefault(node.name, []).append(claim)
        return {name: list[JsonValue](sorted(claims)) for name, claims in sorted(report.items())}

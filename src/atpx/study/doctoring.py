from collections.abc import Iterable, Mapping
from functools import cached_property
from pathlib import Path
from typing import ClassVar

from pydantic import JsonValue

from ..blueprint.manifest import Blueprint
from ..core.certificate import Certificate
from ..core.evidence import EvidenceStore
from ..core.repository import Repository
from ..graph.node import Node
from ..graph.store import NodeStore
from ..support.naming import Naming


class DoctorReport:
    """What needs repair in one workspace: broken claims, stale evidence, untidy directories.

    The lint the tolerant readers rely on. Reports and never mutates. Its findings split
    in two, and `breakages` names which half a finding falls in. A breakage contradicts
    what the workspace itself asserts, a status outside the lifecycle ladder, a wikilink
    pointing at nothing, a claim whose newest evidence failed, never ran, or predates the
    node statement it is meant to support. Everything else is untidiness the capture-first
    posture deliberately tolerates, reported so it can be cleaned up but never a gate.
    """

    BREAKING: ClassVar[tuple[str, ...]] = (
        "invalid_statuses",
        "dangling_links",
        "failing_claims",
        "unevidenced_claims",
        "stale_claims",
    )

    def __init__(self, nodes: NodeStore, *, blueprints: Path, root: Path) -> None:
        """nodes: the blueprint node graph whose statuses are linted.

        blueprints: the blueprints root directory.
        root: the workspace root paths report relative to.
        """
        self.nodes = nodes
        self.blueprints = blueprints
        self.root = root
        self.repository = Repository(root)

    @classmethod
    def breakages(cls, report: Mapping[str, JsonValue]) -> list[str]:
        """The names of the findings in `report` that contradict the workspace's own claims.

        report: a compiled report, this workspace's or another's.
        """
        return [name for name in cls.BREAKING if report.get(name)]

    def compiled(self) -> dict[str, JsonValue]:
        """The full report, one key per lint, breakages first."""
        return {
            "invalid_statuses": self.invalid_statuses(),
            "dangling_links": self.dangling(),
            "failing_claims": self.failing_claims(),
            "unevidenced_claims": self.unevidenced_claims(),
            "stale_claims": self.stale_claims(),
            "stray_evidence": self.stray_evidence(),
            "unmanifested_blueprints": self.unmanifested(),
            "nodeless_blueprints": self.nodeless(),
        }

    def dangling(self) -> dict[str, JsonValue]:
        """Wikilinks and typed relations pointing at slugs with no blueprint directory."""
        report: dict[str, JsonValue] = {}
        for node in self.nodes.nodes():
            targets = dict.fromkeys(
                [*node.links, *(slug for slugs in node.relations.values() for slug in slugs)]
            )
            missing = [slug for slug in targets if not (self.blueprints / slug).is_dir()]
            if missing:
                report[node.name] = list[JsonValue](missing)
        return report

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

    def invalid_statuses(self) -> dict[str, JsonValue]:
        """Nodes carrying a status string outside the lifecycle ladder, or none at all."""
        return {node.name: node.raw_status for node in self.nodes.nodes() if node.status is None}

    def nodeless(self) -> list[JsonValue]:
        """Blueprints holding a manifest or evidence but no `node.md`."""
        return list[JsonValue](
            sorted(
                directory.name
                for directory in self.blueprints.iterdir()
                if directory.is_dir()
                and not (directory / Node.FILENAME).exists()
                and ((directory / Naming.CONFIG).exists() or (directory / "evidence").is_dir())
            )
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

    def stray_evidence(self) -> dict[str, JsonValue]:
        """Files under `evidence/` that are not certificate ledgers, per blueprint."""
        return {
            directory.name: [str(path.relative_to(self.root)) for path in stray]
            for directory in sorted(self.blueprints.iterdir())
            if directory.is_dir() and (stray := EvidenceStore.strays(directory))
        }

    def unevidenced_claims(self) -> dict[str, JsonValue]:
        """Declared claims no host has ever certified, per blueprint."""
        return self.__grouped(
            (node, claim) for node, claim, certificate in self.__evidence if certificate is None
        )

    def unmanifested(self) -> list[JsonValue]:
        """Blueprint directories without a claim manifest."""
        return list[JsonValue](
            sorted(
                directory.name
                for directory in self.blueprints.iterdir()
                if directory.is_dir() and not (directory / Naming.CONFIG).exists()
            )
        )

    @cached_property
    def __evidence(self) -> list[tuple[Node, str, Certificate | None]]:
        """Every declared claim of every node, paired with its newest certificate or None.

        The one walk the three evidence lints share, read once per report so a blueprint's
        manifest and its ledgers are not reopened per lint.
        """
        rows = []
        for node in self.nodes.nodes():
            if not (node.directory / Naming.CONFIG).exists():
                continue
            latest = EvidenceStore.newest(node.directory, node.name)
            claims = Blueprint.load(node.directory).claims
            rows += [(node, claim, latest.get(claim)) for claim in claims]
        return rows

    def __grouped(self, findings: Iterable[tuple[Node, str]]) -> dict[str, JsonValue]:
        """Claim findings collected under their blueprint name, each list sorted.

        findings: (node, claim) pairs one lint flagged.
        """
        report: dict[str, list[str]] = {}
        for node, claim in findings:
            report.setdefault(node.name, []).append(claim)
        return {name: list[JsonValue](sorted(claims)) for name, claims in sorted(report.items())}

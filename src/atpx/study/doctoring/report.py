from collections.abc import Mapping
from pathlib import Path
from typing import ClassVar

from pydantic import JsonValue

from ...graph.store import NodeStore
from ..index import LedgerIndex
from .claims import ClaimLints
from .completeness import CompletenessLints
from .tidiness import TidinessLints


class DoctorReport:
    """What needs repair in one workspace: broken claims, incomplete nodes, untidy shape.

    The lint the tolerant readers rely on. Reports and never mutates. Its findings split
    in two, and `breakages` names which half a finding falls in. A breakage contradicts
    what the workspace itself asserts or leaves a node below the completeness contract:
    a status outside the lifecycle ladder, a wikilink pointing at nothing, a claim whose
    newest evidence failed, never ran, or predates the node statement it supports,
    frontmatter that does not parse, a node without a statement of record or a refutation
    condition, a sketched node whose linked judgment is missing or names no attacking
    rung, a statement that drifted from its judgment snapshot, or an index a regeneration
    would change. Everything else is untidiness the capture-first posture deliberately
    tolerates, reported so it can be cleaned up but never a gate.
    """

    BREAKING: ClassVar[tuple[str, ...]] = (
        "invalid_statuses",
        "dangling_links",
        "failing_claims",
        "unevidenced_claims",
        "stale_claims",
        "frontmatter_problems",
        "unstated_nodes",
        "unconditioned_nodes",
        "unjudged_sketches",
        "drifted_statements",
        "stale_index",
    )

    def __init__(
        self, nodes: NodeStore, *, blueprints: Path, root: Path, index: LedgerIndex
    ) -> None:
        """nodes: the blueprint node graph whose statuses are linted.

        blueprints: the blueprints root directory.
        root: the workspace root paths report relative to.
        index: the workspace's generated index artifacts, checked for currency.
        """
        self.completeness = CompletenessLints(nodes, blueprints=blueprints, root=root)
        self.claims = ClaimLints(nodes, root=root)
        self.tidiness = TidinessLints(nodes, blueprints=blueprints, root=root, index=index)

    @classmethod
    def breakages(cls, report: Mapping[str, JsonValue]) -> list[str]:
        """The names of the findings in `report` that contradict the workspace's own claims.

        report: a compiled report, this workspace's or another's.
        """
        return [name for name in cls.BREAKING if report.get(name)]

    def compiled(self) -> dict[str, JsonValue]:
        """The full report, one key per lint across the three groups, breakages first."""
        found = {
            **self.completeness.compiled(),
            **self.claims.compiled(),
            **self.tidiness.compiled(),
        }
        untidy = [name for name in found if name not in self.BREAKING]
        return {name: found[name] for name in [*self.BREAKING, *untidy]}

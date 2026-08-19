from datetime import UTC, datetime
from pathlib import Path

from ..graph.kind import Kind
from ..graph.node import Node
from ..support.naming import Naming

_SPEC = "claim-spec.md"

_NODE_TEMPLATE = """\
---
status: open
kind: {kind}
date: {date}
references: []
---

# {slug}

## Statement

<!-- one precise claim: quantifiers explicit, symbols defined, deps as [[wikilinks]] -->

## Proof

<!-- the argument or its sketch; name each missing step as its own [[node]] -->

## Evidence

<!-- claim ids and the key numbers their certificates measured -->

## Log    (append-only: [who/tag YYYY-MM-DD] one line)
"""

_SPEC_TEMPLATE = """\
# Claim spec for {slug}

## Claim

<!-- the exact statement one probe certifies, symbols and ranges pinned -->

## Tolerances

<!-- per quantity: the numeric tolerance and why it suffices -->

Feasibility check: reference computation performed? Y/N + numbers

## Emulation hints

<!-- the cheap stand-in: sizes, dtypes, seeds, closed forms to compare against -->

## Exit contract

<!-- sys.exit(0) exactly when every case passes; print at least three name=value lines -->
"""


class Scaffold:
    """Templates one fresh blueprint: node.md, probes/, and a specs/claim-spec.md."""

    def __init__(self, blueprints: Path) -> None:
        """blueprints: the blueprints root directory."""
        self.blueprints = blueprints

    def open(self, slug: str, kind: Kind) -> Path:
        """Create the blueprint skeleton for `slug`, refusing an existing node.

        The node opens with status `open` and its kind stamped in the
        frontmatter; the claim-spec template carries the mandatory feasibility
        check block the prover reads. An existing manifest or spec is kept,
        an existing `node.md` is never overwritten.

        slug: the blueprint directory name, a single path segment.
        kind: the node kind stamped in the frontmatter.
        """
        if "/" in slug:
            raise ValueError(f"slugs are single path segments, got {slug!r}")
        directory = self.blueprints / slug
        node = directory / Node.FILENAME
        if node.exists():
            raise FileExistsError(f"{slug} already has a node at {node}, refusing to overwrite")
        self.__furnished(directory, slug)
        today = datetime.now(UTC).date().isoformat()
        node.write_text(_NODE_TEMPLATE.format(slug=slug, kind=kind.value, date=today))
        return node

    @staticmethod
    def __furnished(directory: Path, slug: str) -> None:
        """Create the probes and specs directories, the manifest, and the claim spec."""
        (directory / "probes").mkdir(parents=True, exist_ok=True)
        (directory / "specs").mkdir(exist_ok=True)
        manifest = directory / Naming.CONFIG
        if not manifest.exists():
            manifest.write_text("[claims]\n")
        spec = directory / "specs" / _SPEC
        if not spec.exists():
            spec.write_text(_SPEC_TEMPLATE.format(slug=slug))

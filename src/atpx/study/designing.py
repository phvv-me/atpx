from itertools import count
from pathlib import Path

from ..graph.store import NodeStore
from ..support.clock import today

_TEMPLATE = """\
# Design for {slug}    (pre-registered {date})

Written before the run, frozen once evidence lands; a successor run gets its
own design file. The decision rule below binds the verdict, and any analysis
outside it is exploratory by declaration.

## Hypothesis

<!-- the falsifiable statement this run can kill, quantifiers and scope pinned -->

## Observable

<!-- the exact measured quantity and its estimator, units per the workspace convention -->

## Conditions

<!-- the full condition grid: parameter values, ensemble sizes, admissibility rules -->

## Decision rule

<!-- the pre-registered pass and fail thresholds, sigma gates included -->

## Seed base

{seed}, allocated from the workspace seed registry and recorded in this
node's frontmatter, disjoint from every base any node ever drew.

## Cost estimate

<!-- expected wall-clock, hardware, and spend, stated before dispatch -->

## Exploratory

<!-- confirmatory by default; declare any exploratory analysis here -->
"""


class Design:
    """Scaffolds one AsPredicted-shaped pre-registration file and allocates its seed base.

    The frontmatter `seeds` lists across every node are the allocation registry,
    so a fresh base is disjoint from every base any node ever drew, and the
    allocation is recorded in the node's frontmatter in the same call that
    mints the design file.
    """

    def __init__(self, nodes: NodeStore) -> None:
        """nodes: the blueprint node graph whose frontmatter registry allocates seed bases."""
        self.nodes = nodes

    def allocated(self) -> int:
        """A fresh seed base, today's `YYYYMMDD` times 100 plus the smallest free counter."""
        taken = {seed for node in self.nodes.nodes() for seed in node.front.seeds}
        base = int(today().replace("-", "")) * 100
        return next(seed for offset in count() if (seed := base + offset) not in taken)

    def scaffold(self, slug: str) -> Path:
        """Write `design-<date>.md` in the node directory, refusing a second one per day.

        slug: the blueprint directory name holding the node.
        """
        node = self.nodes.find(slug)
        path = node.directory / f"design-{today()}.md"
        if path.exists():
            raise FileExistsError(f"{path} already exists; edit it or design tomorrow's run")
        seed = self.allocated()
        registry = ", ".join(str(base) for base in [*node.front.seeds, seed])
        node.set_field("seeds", value=f"[{registry}]")
        path.write_text(_TEMPLATE.format(slug=slug, date=today(), seed=seed))
        return path

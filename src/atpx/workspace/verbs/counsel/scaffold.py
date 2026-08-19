from slugify import slugify

from ....graph.kind import Kind
from ....study.scaffolding import Scaffold
from ...foundation import Slug
from ...state import FoundationState


class ScaffoldVerbs(FoundationState):
    """Scaffold a fresh blueprint: templated node.md, probes/, and a claim-spec."""

    def open(self, slug: Slug, *, kind: str) -> str:
        """Scaffold a fresh blueprint: templated node.md, probes/, and a claim-spec.

        Refuses to overwrite an existing node.md. A free-text title slugifies
        into the directory name; an already-valid slug passes through unchanged.

        slug: the blueprint directory name to create under the blueprints root,
            or a free-text title to derive it from.
        kind: one of lemma, theorem, definition, counterexample, experiment.
        """
        normalized = slugify(slug)
        if not normalized:
            raise ValueError(f"{slug!r} slugifies to nothing; use a title with real characters")
        path = Scaffold(self.blueprints).open(normalized, Kind(kind))
        return str(path.relative_to(self.root))

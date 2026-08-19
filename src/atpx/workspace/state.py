from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

from cyclopts import Parameter

from ..blueprint.manifest import Blueprint
from ..core.certificate import Certificate
from ..graph.store import NodeStore
from ..models.lanes import Lanes
from ..running.execution import Running
from ..study.index import ResultsIndex
from .foundation import Slug


class FoundationState(ABC):
    """The `Foundation` state and primitives a verb group draws on, declared once rather than
    inheriting `Foundation` itself.

    `CheckVerbs`, `StudyVerbs`, and `CounselVerbs` each declare this as their
    only base, so they sit beside each other as disjoint mixins over one
    concrete `Foundation` when `Workspace` combines all three, rather than
    each independently subclassing it and forming a diamond. Every member
    below is abstract; `Foundation`, ahead of the three in `Workspace`'s
    method resolution order, is the sole concrete provider, satisfying the
    contract before any of them are ever instantiated together. The state is
    declared as properties rather than fields because the concrete provider
    resolves each one on first use, so opening a workspace never touches the
    filesystem until a verb actually needs it.
    """

    @property
    @abstractmethod
    def blueprints(self) -> Path: ...

    @property
    @abstractmethod
    def lanes(self) -> Lanes: ...

    @property
    @abstractmethod
    def launcher(self) -> Sequence[str]: ...

    @property
    @abstractmethod
    def lean_task(self) -> str: ...

    @property
    @abstractmethod
    def nodes(self) -> NodeStore: ...

    @property
    @abstractmethod
    def results_index(self) -> ResultsIndex: ...

    @property
    @abstractmethod
    def root(self) -> Path: ...

    @property
    @abstractmethod
    def running(self) -> Running: ...

    @abstractmethod
    def filed(self, path: str) -> Path: ...

    @abstractmethod
    def register(
        self, slug: str, *, claim: str, argv: Sequence[str] | None = None
    ) -> Blueprint: ...

    @abstractmethod
    async def run(
        self,
        slug: Slug,
        claim: str,
        *argv: Annotated[str, Parameter(allow_leading_hyphen=True)],
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate: ...

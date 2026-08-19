from collections.abc import Sequence
from typing import Protocol

from pydantic import JsonValue

from .frame import Frame


class SymbolicRegressor(Protocol):
    """The engine seam of the fit lane; a second search engine slots in here."""

    version: str

    def fit(self, features: Frame, target: Sequence[float]) -> None: ...

    def front(self) -> list[JsonValue]: ...

    def predict(self, features: Frame) -> list[float]: ...

    def score(self, features: Frame, target: Sequence[float]) -> float: ...

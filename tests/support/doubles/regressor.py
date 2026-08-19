import types
from collections.abc import Sequence

from .frame import FakeFrame


class FakeRegressor:
    """The slice of the PySRRegressor surface the fit lane touches."""

    def __init__(self, **settings: float | int | str | bool | list[str]) -> None:
        """settings: whatever keyword configuration the fit lane hands PySR."""
        self.settings = settings

    def fit(self, features: FakeFrame, target: Sequence[float]) -> None:
        row = types.SimpleNamespace(complexity=3, loss=0.125, equation="c1*exp(-r)")
        self.equations_ = types.SimpleNamespace(itertuples=lambda: [row])

    def predict(self, features: FakeFrame) -> list[float]:
        return [2.0 for _ in range(len(features))]

    def score(self, features: FakeFrame, target: Sequence[float]) -> float:
        return 0.99

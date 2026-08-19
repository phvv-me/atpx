from collections.abc import Sequence
from importlib import import_module

from pydantic import JsonValue

from .contracts.frame import Frame


class PysrRegressor:
    """PySR behind the `SymbolicRegressor` seam, one deterministic serial search."""

    def __init__(
        self, *, seed: int, niterations: int, unary: Sequence[str], binary: Sequence[str]
    ) -> None:
        """Raises ImportError when pysr is absent, the dormant-lane signal.

        seed: random_state for the certifying run.
        niterations: search budget.
        unary: PySR's `unary_operators`, defaults hold when empty.
        binary: PySR's `binary_operators`, defaults hold when empty.
        """
        pysr = import_module("pysr")
        self.version = str(getattr(pysr, "__version__", "unknown"))
        menu = {"unary_operators": list(unary), "binary_operators": list(binary)}
        self.model = pysr.PySRRegressor(
            niterations=niterations,
            random_state=seed,
            deterministic=True,
            parallelism="serial",
            **{name: operators for name, operators in menu.items() if operators},
        )

    def fit(self, features: Frame, target: Sequence[float]) -> None:
        """Run the search over the training rows."""
        self.model.fit(features, target)

    def front(self) -> list[JsonValue]:
        """The Pareto front of discovered equations, one record per complexity."""
        return [
            {
                "complexity": int(row.complexity),
                "loss": float(row.loss),
                "equation": str(row.equation),
            }
            for row in self.model.equations_.itertuples()
        ]

    def predict(self, features: Frame) -> list[float]:
        """Predictions over the holdout rows, in row order."""
        return [float(value) for value in self.model.predict(features)]

    def score(self, features: Frame, target: Sequence[float]) -> float:
        """R² of the fitted model over the holdout rows."""
        return float(self.model.score(features, target))

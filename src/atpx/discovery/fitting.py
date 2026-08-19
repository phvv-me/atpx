from collections.abc import Iterable, Sequence
from importlib import import_module
from pathlib import Path

from pydantic import JsonValue

from ..core.certificate import Certificate
from .contracts.frame import Frame
from .contracts.regressor import SymbolicRegressor
from .holdouts.random import RandomHoldout
from .holdouts.tail import TailHoldout
from .pysr import PysrRegressor


class Discovery:
    """The fit lane: symbolic regression over a data artifact, certifying the Pareto front.

    The operator menu keeps winners interpretable: a law the operators cannot
    express is only ever matched by an opaque rational. The holdout is scored
    with both R² and NMSE, and the certificate records the split, the menu,
    and the exact feature columns used.
    """

    def __init__(self, root: Path) -> None:
        """root: the workspace root data paths resolve against second."""
        self.root = root

    def dormant(self, data: str, seed: int) -> Certificate:
        """The honest nonzero certificate when pysr is not installed."""
        return Certificate.stamp(
            claim=f"fit {data}",
            result={"error": "pysr is not installed, the fit lane is dormant"},
            engine="pysr",
            engine_version="unknown",
            exit_status=1,
            seed=seed,
            root=self.root,
        )

    def fit(
        self,
        data: str,
        *,
        target: str,
        seed: int = 0,
        niterations: int = 40,
        unary: Sequence[str] | None = None,
        binary: Sequence[str] | None = None,
        tail: float | None = None,
        driver: str | None = None,
        features: Sequence[str] | None = None,
    ) -> Certificate:
        """Fit one data artifact and stamp the certificate, honest when dormant.

        data: path to a CSV, resolved cwd-first and then root-relative.
        target: the column to fit.
        seed: random_state for the certifying run.
        niterations: search budget.
        unary: unary operator menu, repeated flags or comma-joined.
        binary: binary operator menu, repeated flags or comma-joined.
        tail: hold out this fraction of the rows with the largest driver values
            instead of a random 20%.
        driver: the column ranking the tail holdout, defaulting to the first
            feature column.
        features: restrict the fit to these columns, repeated or comma-joined,
            defaulting to every non-target column.
        """
        menu = {"unary": commas(unary), "binary": commas(binary)}
        try:
            regressor: SymbolicRegressor = PysrRegressor(
                seed=seed, niterations=niterations, unary=menu["unary"], binary=menu["binary"]
            )
        except ImportError:
            return self.dormant(data, seed)
        pandas = import_module("pandas")
        frame: Frame = pandas.read_csv(self.located(data))
        columns = commas(features) or [name for name in frame.columns if name != target]
        holdout_policy: RandomHoldout | TailHoldout = (
            TailHoldout(fraction=tail, driver=driver or columns[0])
            if tail is not None
            else RandomHoldout(seed=seed)
        )
        train, holdout = holdout_policy.carve(frame)
        regressor.fit(train[columns], train[target])
        return Certificate.stamp(
            claim=f"fit {data}",
            result={
                "front": regressor.front(),
                "holdout_r2": regressor.score(holdout[columns], holdout[target]),
                "holdout_nmse": nmse(regressor.predict(holdout[columns]), holdout[target]),
                "holdout": holdout_policy.described(),
                "operators": {"unary": [*menu["unary"]], "binary": [*menu["binary"]]},
                "features": list[JsonValue](columns),
                "pysr": regressor.version,
            },
            engine="pysr",
            engine_version=regressor.version,
            seed=seed,
            root=self.root,
        )

    def located(self, data: str) -> Path:
        """The data artifact, resolved cwd-first and then workspace-root-relative.

        data: the path as given, absolute or relative.
        """
        direct = Path(data)
        return direct if direct.exists() else self.root / data


def commas(tokens: Sequence[str] | None) -> list[str]:
    """Flatten repeated flags and comma-joined menus into one token list.

    `--unary exp --unary log` and `--unary exp,log` both yield `["exp", "log"]`.

    tokens: the raw flag values, None when the flag was omitted.
    """
    return [token for item in tokens or [] for token in item.split(",") if token]


def nmse(predicted: Sequence[float], observed: Iterable[float]) -> float | None:
    """Normalized mean squared error, `sum((pred-y)^2) / sum((y-mean)^2)`.

    Plain arithmetic over the values, so pandas Series and ndarray rows both
    work without a numpy dependency here. None when the observed values are
    constant, where the ratio is undefined.

    predicted: model predictions over the holdout rows.
    observed: the true target values, in the same row order.
    """
    actual = [float(value) for value in observed]
    center = sum(actual) / len(actual)
    residual = sum(
        (float(guess) - truth) ** 2 for guess, truth in zip(predicted, actual, strict=True)
    )
    spread = sum((truth - center) ** 2 for truth in actual)
    return residual / spread if spread else None

import json
import sys
import types
from collections.abc import Iterable
from pathlib import Path
from typing import overload

import pytest

from atpx import cli
from atpx.discovery import Discovery, RandomHoldout, TailHoldout, commas, nmse
from atpx.evidence import EvidenceStore
from atpx.workspace import Workspace

from .conftest import FakeRunner, result_of


class FakeModule(types.ModuleType):
    """A stand-in for an optional dependency, its attributes fixed at construction."""

    def __init__(self, name: str, **attributes: object) -> None:
        super().__init__(name)
        vars(self).update(attributes)


class FakeFrame:
    """The slice of the pandas frame surface the fit lane touches."""

    def __init__(self, columns: list[str], rows: list[list[float]] | None = None) -> None:
        self.columns = columns
        self.rows = rows if rows is not None else [[1.0, 2.0], [3.0, 4.0]]
        self.index = list(range(len(self.rows)))

    def __len__(self) -> int:
        return len(self.rows)

    def sample(self, n: int, random_state: int) -> FakeFrame:
        return FakeFrame(self.columns, self.rows[:n])

    def nlargest(self, count: int, column: str) -> FakeFrame:
        at = self.columns.index(column)
        ordered = sorted(self.rows, key=lambda row: row[at], reverse=True)
        return FakeFrame(self.columns, ordered[:count])

    def drop(self, index: Iterable[int]) -> FakeFrame:
        return FakeFrame(self.columns, self.rows)

    @overload
    def __getitem__(self, key: str) -> list[float]: ...

    @overload
    def __getitem__(self, key: list[str]) -> FakeFrame: ...

    def __getitem__(self, key: str | list[str]) -> list[float] | FakeFrame:
        if isinstance(key, str):
            at = self.columns.index(key)
            return [row[at] for row in self.rows]
        return FakeFrame(key, self.rows)


class FakeRegressor:
    """The slice of the PySRRegressor surface the fit lane touches."""

    def __init__(self, **settings: object) -> None:
        self.settings = settings

    def fit(self, features: FakeFrame, target: list[float]) -> None:
        row = types.SimpleNamespace(complexity=3, loss=0.125, equation="c1*exp(-r)")
        self.equations_ = types.SimpleNamespace(itertuples=lambda: [row])

    def score(self, features: FakeFrame, target: list[float]) -> float:
        return 0.99

    def predict(self, features: FakeFrame) -> list[float]:
        return [2.0 for _ in range(len(features))]


@pytest.fixture
def lane(monkeypatch: pytest.MonkeyPatch) -> list[FakeRegressor]:
    """Install fake pysr and pandas modules; returns every regressor pysr builds."""
    built: list[FakeRegressor] = []

    class RecordingRegressor(FakeRegressor):
        def __init__(self, **settings: object) -> None:
            super().__init__(**settings)
            built.append(self)

    rows = [[1.0, 2.0], [2.0, 3.0], [3.0, 4.0], [4.0, 6.0]]
    pysr = FakeModule("pysr", PySRRegressor=RecordingRegressor, __version__="9.9.9")
    pandas = FakeModule("pandas", read_csv=lambda path: FakeFrame(["rate", "distortion"], rows))
    monkeypatch.setitem(sys.modules, "pysr", pysr)
    monkeypatch.setitem(sys.modules, "pandas", pandas)
    return built


def test_fit_certifies_the_pareto_front(
    ws: tuple[Workspace, FakeRunner], lane: list[FakeRegressor]
) -> None:
    space, runner = ws
    certificate = space.fit("data.csv", "distortion", slug="demo", seed=3)
    assert certificate.ok and certificate.engine == "pysr"
    result = result_of(certificate)
    assert result["front"] == [{"complexity": 3, "loss": 0.125, "equation": "c1*exp(-r)"}]
    assert result["holdout_r2"] == 0.99
    assert result["holdout"] == {"mode": "random", "fraction": 0.2, "driver": None}
    assert result["operators"] == {"unary": [], "binary": []}
    assert result["features"] == ["rate"]
    assert result["pysr"] == "9.9.9"
    assert lane[0].settings == {
        "niterations": 40,
        "random_state": 3,
        "deterministic": True,
        "parallelism": "serial",
    }
    claims = [entry.claim for entry in EvidenceStore(space.blueprints / "demo").read()]
    assert "fit data.csv" in claims


def test_fit_tail_holdout_and_operator_menu(
    ws: tuple[Workspace, FakeRunner], lane: list[FakeRegressor]
) -> None:
    space, runner = ws
    certificate = space.fit("data.csv", "distortion", tail=0.5, unary=["exp"], binary=["+", "*"])
    result = result_of(certificate)
    assert result["holdout"] == {"mode": "tail", "fraction": 0.5, "driver": "rate"}
    assert result["holdout_nmse"] == 10.0
    assert result["operators"] == {"unary": ["exp"], "binary": ["+", "*"]}
    assert lane[0].settings["unary_operators"] == ["exp"]
    assert lane[0].settings["binary_operators"] == ["+", "*"]


def test_fit_splits_comma_joined_menus(
    ws: tuple[Workspace, FakeRunner], lane: list[FakeRegressor]
) -> None:
    space, runner = ws
    certificate = space.fit("data.csv", "distortion", unary=["exp,log"], binary=["+,-,*"])
    result = result_of(certificate)
    assert result["operators"] == {"unary": ["exp", "log"], "binary": ["+", "-", "*"]}
    assert lane[0].settings["unary_operators"] == ["exp", "log"]
    assert lane[0].settings["binary_operators"] == ["+", "-", "*"]


def test_fit_restricts_features_and_records_them(
    ws: tuple[Workspace, FakeRunner], lane: list[FakeRegressor], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    frame = FakeFrame(["rate", "noise", "distortion"], [[1.0, 9.0, 2.0], [2.0, 8.0, 3.0]])
    monkeypatch.setattr(sys.modules["pandas"], "read_csv", lambda path: frame)
    certificate = space.fit("data.csv", "distortion", features=["rate"], tail=0.5)
    result = result_of(certificate)
    assert result["features"] == ["rate"]
    assert result["holdout"]["driver"] == "rate"


def test_fit_tail_honors_an_explicit_driver(
    ws: tuple[Workspace, FakeRunner], lane: list[FakeRegressor], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    frame = FakeFrame(["rate", "noise", "distortion"], [[1.0, 9.0, 2.0], [2.0, 8.0, 3.0]])
    monkeypatch.setattr(sys.modules["pandas"], "read_csv", lambda path: frame)
    certificate = space.fit("data.csv", "distortion", tail=0.5, driver="noise")
    assert result_of(certificate)["holdout"]["driver"] == "noise"


def test_fit_without_a_slug_returns_an_unpersisted_certificate(
    ws: tuple[Workspace, FakeRunner], lane: list[FakeRegressor]
) -> None:
    space, runner = ws
    certificate = space.fit("data.csv", "distortion")
    assert certificate.ok
    assert EvidenceStore.ledgers(space.blueprints / "demo") == {}


def test_fit_is_dormant_without_pysr(root: Path) -> None:
    certificate = Discovery(root).fit(
        "data.csv",
        "distortion",
        seed=0,
        niterations=40,
        unary=None,
        binary=None,
        tail=None,
        driver=None,
        features=None,
    )
    assert certificate.exit_status == 1 and certificate.engine_version == "unknown"
    assert result_of(certificate)["error"].startswith("pysr is not installed")


def test_located_prefers_the_cwd_then_the_root(
    root: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path_factory.mktemp("scratch")
    (elsewhere / "data.csv").write_text("rate,distortion\n1,2\n")
    monkeypatch.chdir(elsewhere)
    discovery = Discovery(root)
    assert discovery.located("data.csv") == Path("data.csv")
    assert discovery.located("missing.csv") == root / "missing.csv"


def test_commas_flattens_repeats_and_joins() -> None:
    assert commas(None) == []
    assert commas(["exp", "log"]) == ["exp", "log"]
    assert commas(["exp,log", "sqrt"]) == ["exp", "log", "sqrt"]
    assert commas(["a,,b", ""]) == ["a", "b"]


def test_nmse_scores_the_holdout() -> None:
    assert nmse([2.0, 2.0], [6.0, 4.0]) == 10.0
    assert nmse([1.0, 1.0], [3.0, 3.0]) is None


def test_cli_fit_collects_repeated_operator_flags(
    ws: tuple[Workspace, FakeRunner],
    lane: list[FakeRegressor],
    capsys: pytest.CaptureFixture[str],
) -> None:
    space, runner = ws
    argv = ["fit", "data.csv", "distortion", "--unary", "exp", "--unary", "log"]
    cli.build(space)([*argv, "--tail", "0.5", "--driver", "rate"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["result"]["operators"] == {"unary": ["exp", "log"], "binary": []}
    assert certificate["result"]["holdout"] == {"mode": "tail", "fraction": 0.5, "driver": "rate"}


def test_cli_fit_accepts_comma_menus_and_features(
    ws: tuple[Workspace, FakeRunner],
    lane: list[FakeRegressor],
    capsys: pytest.CaptureFixture[str],
) -> None:
    space, runner = ws
    argv = ["fit", "data.csv", "distortion", "--unary", "exp,log", "--binary", "+,-,*"]
    cli.build(space)([*argv, "--features", "rate"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["result"]["operators"] == {
        "unary": ["exp", "log"],
        "binary": ["+", "-", "*"],
    }
    assert certificate["result"]["features"] == ["rate"]


def test_cli_fit_accepts_a_bare_hyphen_through_equals(
    ws: tuple[Workspace, FakeRunner],
    lane: list[FakeRegressor],
    capsys: pytest.CaptureFixture[str],
) -> None:
    space, runner = ws
    cli.build(space)(["fit", "data.csv", "distortion", "--binary=-"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["result"]["operators"] == {"unary": [], "binary": ["-"]}


def test_holdouts_never_round_down_to_zero_rows() -> None:
    frame = FakeFrame(["rate", "distortion"], [[1.0, 2.0], [2.0, 3.0]])
    train, held = RandomHoldout(seed=0).carve(frame)
    assert len(held) == 1
    train, held = TailHoldout(fraction=0.1, driver="rate").carve(frame)
    assert len(held) == 1

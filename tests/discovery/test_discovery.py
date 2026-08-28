import json
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

from atpx import EvidenceStore, Workspace, cli
from atpx.discovery import RandomHoldout, TailHoldout
from atpx.discovery.fitting import Discovery, commas, nmse

from ..support import FakeFrame, FakeModule, FakeRegressor, result_of

_OPERATORS = "operators"


@pytest.fixture
def lane(monkeypatch: pytest.MonkeyPatch) -> list[FakeRegressor]:
    """Install fake pysr and pandas modules; returns every regressor pysr builds."""
    built: list[FakeRegressor] = []

    class RecordingRegressor(FakeRegressor):
        def __init__(self, **settings: float | int | str | bool | list[str]) -> None:
            super().__init__(**settings)
            built.append(self)

    rows = [[1.0, 2.0], [2.0, 3.0], [3.0, 4.0], [4.0, 6.0]]
    pysr = FakeModule("pysr", PySRRegressor=RecordingRegressor, __version__="9.9.9")
    pandas = FakeModule("pandas", read_csv=lambda path: FakeFrame(["rate", "distortion"], rows))
    monkeypatch.setitem(sys.modules, "pysr", pysr)
    monkeypatch.setitem(sys.modules, "pandas", pandas)
    return built


def test_fit_certifies_the_pareto_front(space: Workspace, lane: Sequence[FakeRegressor]) -> None:
    certificate = space.fit("data.csv", "distortion", slug="demo", seed=3)
    assert certificate.ok and certificate.engine == "pysr"
    result = result_of(certificate)
    assert result["front"] == [{"complexity": 3, "loss": 0.125, "equation": "c1*exp(-r)"}]
    assert result["holdout_r2"] == 0.99 and result["pysr"] == "9.9.9"
    assert result["holdout"] == {"mode": "random", "fraction": 0.2, "driver": None}
    assert result[_OPERATORS] == {"unary": [], "binary": []}
    assert result["features"] == ["rate"]
    claims = [entry.claim for entry in EvidenceStore(space.nodes.directory("demo")).read()]
    assert "fit data.csv" in claims


def test_fit_configures_pysr_deterministically(
    space: Workspace, lane: Sequence[FakeRegressor]
) -> None:
    space.fit("data.csv", "distortion", slug="demo", seed=3)
    assert lane[0].settings == {
        "niterations": 40,
        "random_state": 3,
        "deterministic": True,
        "parallelism": "serial",
    }


def test_fit_tail_holdout_and_operator_menu(
    space: Workspace, lane: Sequence[FakeRegressor]
) -> None:
    certificate = space.fit("data.csv", "distortion", tail=0.5, unary=["exp"], binary=["+", "*"])
    result = result_of(certificate)
    assert result["holdout"] == {"mode": "tail", "fraction": 0.5, "driver": "rate"}
    assert result["holdout_nmse"] == 10.0
    assert result[_OPERATORS] == {"unary": ["exp"], "binary": ["+", "*"]}
    assert lane[0].settings["unary_operators"] == ["exp"]
    assert lane[0].settings["binary_operators"] == ["+", "*"]


def test_fit_splits_comma_joined_menus(space: Workspace, lane: Sequence[FakeRegressor]) -> None:
    certificate = space.fit("data.csv", "distortion", unary=["exp,log"], binary=["+,-,*"])
    result = result_of(certificate)
    assert result[_OPERATORS] == {"unary": ["exp", "log"], "binary": ["+", "-", "*"]}
    assert lane[0].settings["unary_operators"] == ["exp", "log"]
    assert lane[0].settings["binary_operators"] == ["+", "-", "*"]


def test_fit_restricts_features_and_records_them(
    space: Workspace, lane: Sequence[FakeRegressor], monkeypatch: pytest.MonkeyPatch
) -> None:
    frame = FakeFrame(["rate", "noise", "distortion"], [[1.0, 9.0, 2.0], [2.0, 8.0, 3.0]])
    monkeypatch.setattr(sys.modules["pandas"], "read_csv", lambda path: frame)
    certificate = space.fit("data.csv", "distortion", features=["rate"], tail=0.5)
    result = result_of(certificate)
    assert result["features"] == ["rate"]
    assert result["holdout"]["driver"] == "rate"


def test_fit_tail_honors_an_explicit_driver(
    space: Workspace, lane: Sequence[FakeRegressor], monkeypatch: pytest.MonkeyPatch
) -> None:
    frame = FakeFrame(["rate", "noise", "distortion"], [[1.0, 9.0, 2.0], [2.0, 8.0, 3.0]])
    monkeypatch.setattr(sys.modules["pandas"], "read_csv", lambda path: frame)
    certificate = space.fit("data.csv", "distortion", tail=0.5, driver="noise")
    assert result_of(certificate)["holdout"]["driver"] == "noise"


def test_fit_without_a_slug_returns_an_unpersisted_certificate(
    space: Workspace, lane: Sequence[FakeRegressor]
) -> None:
    certificate = space.fit("data.csv", "distortion")
    assert certificate.ok
    assert EvidenceStore.ledgers(space.nodes.directory("demo")) == {}


def test_fit_is_honest_about_a_dormant_lane_and_never_persists_it(
    space: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "pysr", None)
    certificate = space.fit("data.csv", "distortion", slug="demo")
    assert certificate.exit_status == 1
    assert "pysr" in json.dumps(certificate.result)
    assert EvidenceStore.ledgers(space.nodes.directory("demo")) == {}


def test_fit_is_dormant_without_pysr(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pysr", None)
    certificate = Discovery(root).fit("data.csv", target="distortion")
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
    space: Workspace,
    lane: Sequence[FakeRegressor],
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["fit", "data.csv", "distortion", "--unary", "exp", "--unary", "log"]
    cli.build(space)([*argv, "--tail", "0.5", "--driver", "rate"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["result"][_OPERATORS] == {"unary": ["exp", "log"], "binary": []}
    assert certificate["result"]["holdout"] == {"mode": "tail", "fraction": 0.5, "driver": "rate"}


def test_cli_fit_accepts_comma_menus_and_features(
    space: Workspace,
    lane: Sequence[FakeRegressor],
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["fit", "data.csv", "distortion", "--unary", "exp,log", "--binary", "+,-,*"]
    cli.build(space)([*argv, "--features", "rate"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["result"][_OPERATORS] == {
        "unary": ["exp", "log"],
        "binary": ["+", "-", "*"],
    }
    assert certificate["result"]["features"] == ["rate"]


def test_cli_fit_accepts_a_bare_hyphen_through_equals(
    space: Workspace,
    lane: Sequence[FakeRegressor],
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.build(space)(["fit", "data.csv", "distortion", "--binary=-"])
    certificate = json.loads(capsys.readouterr().out)
    assert certificate["result"][_OPERATORS] == {"unary": [], "binary": ["-"]}


def test_holdouts_never_round_down_to_zero_rows() -> None:
    frame = FakeFrame(["rate", "distortion"], [[1.0, 2.0], [2.0, 3.0]])
    train, held = RandomHoldout(seed=0).carve(frame)
    assert len(held) == 1
    train, held = TailHoldout(fraction=0.1, driver="rate").carve(frame)
    assert len(held) == 1

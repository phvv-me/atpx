import os
import stat
import sys
import types
from decimal import Decimal
from importlib.machinery import ModuleSpec
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx.engines import (
    Capability,
    Cvc5Engine,
    Engine,
    EngineUnavailableError,
    EProverEngine,
    FlintEngine,
    MpmathEngine,
    PariEngine,
    SympyEngine,
    UnsupportedOperationError,
    VampireEngine,
    Z3Engine,
    normalized,
)
from atpx.engines.base import importable

UNSAT = "(set-logic QF_LIA)(declare-const x Int)(assert (> x 0))(assert (< x 0))"
SAT = "(set-logic QF_LIA)(declare-const x Int)(assert (> x 0))"

decimals = st.decimals(
    allow_nan=False,
    allow_infinity=False,
    places=8,
    min_value=Decimal("-1e12"),
    max_value=Decimal("1e12"),
)


@given(decimals)
def test_normalization_is_idempotent_and_format_blind(value: Decimal) -> None:
    canonical = normalized(Capability.EVALUATE, str(value))
    assert normalized(Capability.EVALUATE, canonical) == canonical
    assert normalized(Capability.EVALUATE, str(value * Decimal("1.000"))) == canonical
    assert normalized(Capability.EVALUATE, value.to_eng_string()) == canonical


def test_non_numeric_results_compare_verbatim() -> None:
    assert normalized(Capability.SOLVE_SMT, " unsat\n") == "unsat"


def test_sympy_and_mpmath_evaluate_agree_independently() -> None:
    results = {
        normalized(Capability.EVALUATE, engine().run("evaluate", "pi*exp(1)"))
        for engine in (SympyEngine, MpmathEngine)
    }
    assert len(results) == 1
    assert results.pop().startswith("8.53973422267356706")


def test_flint_factors_exactly() -> None:
    assert FlintEngine().run("factor", "720") == "2^4 3^2 5^1"


def test_smt_solvers_agree_on_sat_and_unsat() -> None:
    for engine in (Z3Engine, Cvc5Engine):
        assert engine().run("solve-smt", UNSAT) == "unsat"
        assert engine().run("solve-smt", SAT) == "sat"


def test_engines_refuse_foreign_operations() -> None:
    with pytest.raises(UnsupportedOperationError, match="only does evaluate"):
        SympyEngine().run("factor", "12")


def test_engine_versions_come_from_the_distribution() -> None:
    assert SympyEngine().version()[0].isdigit()
    assert Z3Engine().version()[0].isdigit()


def test_supporting_preserves_preference_order() -> None:
    assert Engine.supporting("solve-smt") == [Z3Engine, Cvc5Engine]
    assert Engine.supporting(Capability.PROVE_TPTP) == [EProverEngine, VampireEngine]


def test_importable_is_a_safe_probe() -> None:
    assert importable("json")
    assert not importable("no_such_module_anywhere")
    assert not importable("no_such_package.no_such_module")


class FakePari:
    """Stand-in for cypari2.Pari returning a fixed factorization."""

    def factor(self, n: int) -> list[list[int]]:
        assert n == 720
        return [[2, 3, 5], [4, 2, 1]]


def test_pari_is_linux_only(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = PariEngine()
    monkeypatch.setattr(PariEngine, "platform", "darwin")
    assert not engine.available()
    with pytest.raises(EngineUnavailableError, match="pari"):
        engine.run("factor", "720")


def test_pari_factors_match_flint_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.ModuleType("cypari2")
    fake.__spec__ = ModuleSpec("cypari2", None)
    monkeypatch.setattr(fake, "Pari", FakePari, raising=False)
    monkeypatch.setitem(sys.modules, "cypari2", fake)
    monkeypatch.setattr(PariEngine, "platform", "linux")
    engine = PariEngine()
    assert engine.available()
    assert engine.run("factor", "720") == FlintEngine().run("factor", "720")
    assert engine.version() in {"unknown", "2.2.4"}


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    return tmp_path


def script(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_subprocess_provers_parse_szs_status(fake_bin: Path) -> None:
    script(
        fake_bin,
        "eprover",
        'if [ "$1" = "--version" ]; then echo "E 3.1"; else echo "# SZS status Theorem"; fi',
    )
    script(fake_bin, "vampire", 'echo "% SZS status CounterSatisfiable for $1"')
    eprover, vampire = EProverEngine(), VampireEngine()
    assert eprover.available() and vampire.available()
    assert eprover.version() == "E 3.1"
    assert eprover.run("prove-tptp", "fof(g, conjecture, a => a).") == "Theorem"
    assert vampire.run("prove-tptp", "fof(g, conjecture, a => ~a).") == "CounterSatisfiable"


def test_a_silent_prover_reports_unknown(fake_bin: Path) -> None:
    script(fake_bin, "eprover", "true")
    assert EProverEngine().run("prove-tptp", "fof(g, conjecture, a).") == "Unknown"


def test_provers_are_unavailable_without_the_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    assert not EProverEngine().available()
    assert not VampireEngine().available()

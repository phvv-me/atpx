import os
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
    PariEngine,
    SympyEngine,
    UnsupportedOperationError,
    VampireEngine,
    Z3Engine,
    normalized,
)
from atpx.engines.base import importable

from .conftest import script

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
    assert normalized(Capability.SOLVE_SMT, " unsat\n") == "unsat"


def test_flint_factors_into_the_canonical_product_string() -> None:
    assert FlintEngine().run("factor", "720") == "2^4 3^2 5^1"


def test_engines_refuse_foreign_operations() -> None:
    with pytest.raises(UnsupportedOperationError, match="only does evaluate"):
        SympyEngine().run("factor", "12")


def test_engine_versions_come_from_the_distribution() -> None:
    assert SympyEngine().version()[0].isdigit()
    assert Z3Engine().version()[0].isdigit()


def test_supporting_preserves_preference_order() -> None:
    assert Engine.supporting("solve-smt") == [Z3Engine, Cvc5Engine]
    assert Engine.supporting(Capability.PROVE_TPTP) == [EProverEngine, VampireEngine]


@pytest.mark.parametrize(
    ("module", "present"),
    [("json", True), ("no_such_module_anywhere", False), ("no_such_pkg.no_such_module", False)],
)
def test_importable_is_a_safe_probe(module: str, present: bool) -> None:
    assert importable(module) is present


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

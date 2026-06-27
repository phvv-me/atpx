from pathlib import Path

import pytest

from atpx.blueprint import REQUIREMENTS, Blueprint, Claim, satisfied


def test_load_reads_the_manifest(root: Path) -> None:
    blueprint = Blueprint.load(root / "research" / "math" / "demo")
    assert blueprint.slug == "demo"
    assert blueprint.zettel == "Demo Node"
    assert blueprint.claims == {
        "ok": Claim(command="python {dir}/checks.py ok"),
        "gpu": Claim(command="python {dir}/checks.py gpu", requires="cuda"),
    }


def test_command_expands_the_directory_placeholder(root: Path) -> None:
    blueprint = Blueprint.load(root / "research" / "math" / "demo")
    assert blueprint.command("ok", root) == [
        "python",
        "research/math/demo/checks.py",
        "ok",
    ]


def test_load_names_a_missing_blueprint(root: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no blueprint 'ghost'"):
        Blueprint.load(root / "research" / "math" / "ghost")


def test_an_unknown_claim_lists_the_known_ones(root: Path) -> None:
    blueprint = Blueprint.load(root / "research" / "math" / "demo")
    with pytest.raises(KeyError, match="known claims are gpu, ok"):
        blueprint.command("missing", root)


def test_satisfied_probes_the_requirement_vocabulary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: True)
    assert satisfied("cuda")
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: False)
    assert not satisfied("cuda")
    with pytest.raises(KeyError, match="unknown requirement 'quantum'"):
        satisfied("quantum")

import tomllib
from pathlib import Path

import pytest

from atpx import Blueprint, Claim
from atpx.blueprint.claim import is_satisfied

_CONFIG = "atpx.toml"
_MATH = "research/math"


def test_load_reads_the_manifest(root: Path) -> None:
    blueprint = Blueprint.load(root / _MATH / "demo")
    assert blueprint.slug == "demo"
    assert blueprint.claims == {
        "ok": Claim(command="python {dir}/checks.py ok"),
        "gpu": Claim(command="python {dir}/checks.py gpu", requires="cuda"),
    }


def test_command_expands_the_directory_placeholder_to_a_full_path(root: Path) -> None:
    """Absolute, since the launcher decides which directory a claim actually runs from."""
    blueprint = Blueprint.load(root / _MATH / "demo")
    assert blueprint.command("ok") == [
        "python",
        f"{root / _MATH / 'demo'}/checks.py",
        "ok",
    ]


def test_load_names_a_missing_blueprint(root: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no blueprint 'ghost'"):
        Blueprint.load(root / _MATH / "ghost")


def test_an_unknown_claim_lists_the_known_ones(root: Path) -> None:
    blueprint = Blueprint.load(root / _MATH / "demo")
    with pytest.raises(KeyError, match="known claims are gpu, ok"):
        blueprint.command("missing")


def test_an_unknown_claim_close_to_a_known_one_suggests_it(root: Path) -> None:
    blueprint = Blueprint.load(root / _MATH / "demo")
    with pytest.raises(KeyError, match="did you mean 'ok'\\? known claims are gpu, ok"):
        blueprint.command("okk")


def test_a_malformed_claims_table_is_a_clean_error(root: Path) -> None:
    directory = root / _MATH / "broken"
    directory.mkdir()
    (directory / _CONFIG).write_text('zettel = "B"\nclaims = 5\n')
    with pytest.raises(ValueError, match="claims"):
        Blueprint.load(directory)


def test_load_tolerates_a_legacy_zettel_key_and_a_missing_claims_table(root: Path) -> None:
    directory = root / _MATH / "legacy"
    directory.mkdir()
    (directory / _CONFIG).write_text('zettel = "Old Title"\n')
    assert Blueprint.load(directory).claims == {}


def test_is_satisfied_probes_the_requirement_vocabulary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("atpx.blueprint.claim._REQUIREMENTS", {"cuda": lambda: True})
    assert is_satisfied("cuda")
    monkeypatch.setattr("atpx.blueprint.claim._REQUIREMENTS", {"cuda": lambda: False})
    assert not is_satisfied("cuda")
    with pytest.raises(KeyError, match="unknown requirement 'quantum'"):
        is_satisfied("quantum")


def test_register_preserves_claim_tables_on_rewrite(root: Path) -> None:
    blueprints = root / _MATH
    Blueprint.register(blueprints, slug="demo", claim="extra", argv=["echo", "hi"])
    manifest = tomllib.loads((blueprints / "demo" / _CONFIG).read_text())
    assert manifest["claims"]["extra"] == "echo hi"
    assert manifest["claims"]["gpu"] == {
        "command": "python {dir}/checks.py gpu",
        "requires": "cuda",
    }


def test_register_without_a_command_creates_an_empty_manifest(root: Path) -> None:
    blueprints = root / _MATH
    blueprint = Blueprint.register(blueprints, slug="greenfield", claim="lean")
    assert blueprint.claims == {}
    assert tomllib.loads((blueprints / "greenfield" / _CONFIG).read_text()) == {"claims": {}}


def test_register_refuses_path_segments_in_slugs_and_claims(root: Path) -> None:
    blueprints = root / _MATH
    with pytest.raises(ValueError, match="single path segments"):
        Blueprint.register(blueprints, slug="a/b", claim="ok")
    with pytest.raises(ValueError, match="single path segments"):
        Blueprint.register(blueprints, slug="demo", claim="a/b")


def test_register_tolerates_a_malformed_claims_scalar(root: Path) -> None:
    """A manifest whose `claims` is not a table registers nothing and fails on load."""
    directory = root / _MATH / "broken"
    directory.mkdir()
    (directory / _CONFIG).write_text('zettel = "B"\nclaims = 5\n')
    with pytest.raises(ValueError, match="claims"):
        Blueprint.register(root / _MATH, slug="broken", claim="probe", argv=["echo", "hi"])
    assert tomllib.loads((directory / _CONFIG).read_text())["claims"] == 5


def test_register_preserves_a_hand_written_comment(root: Path) -> None:
    """A human comment in `atpx.toml` survives a claim registered afterward."""
    directory = root / _MATH / "demo"
    manifest = directory / _CONFIG
    original = manifest.read_text()
    manifest.write_text("# hand-written note\n" + original)
    Blueprint.register(root / _MATH, slug="demo", claim="extra", argv=["echo", "hi"])
    text = manifest.read_text()
    assert text.startswith("# hand-written note\n")
    assert tomllib.loads(text)["claims"]["extra"] == "echo hi"


def test_register_updates_a_stale_scalar_command(root: Path) -> None:
    """A run with a different command wins over a stale scalar registration.

    The prover writes `probes/<claim>.py` and runs it; a pre-registered path
    must not shadow the command actually executing.
    """
    blueprints = root / _MATH
    Blueprint.register(blueprints, slug="demo", claim="probe", argv=["python", "old_path.py"])
    Blueprint.register(blueprints, slug="demo", claim="probe", argv=["python", "probes/probe.py"])
    manifest = tomllib.loads((blueprints / "demo" / _CONFIG).read_text())
    assert manifest["claims"]["probe"] == "python probes/probe.py"


def test_register_never_flattens_a_claim_table(root: Path) -> None:
    """A claim recorded as a table keeps `requires` even when a run passes argv."""
    blueprints = root / _MATH
    Blueprint.register(blueprints, slug="demo", claim="gpu", argv=["python", "elsewhere.py"])
    manifest = tomllib.loads((blueprints / "demo" / _CONFIG).read_text())
    assert manifest["claims"]["gpu"] == {
        "command": "python {dir}/checks.py gpu",
        "requires": "cuda",
    }

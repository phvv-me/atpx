import tomllib
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import JsonValue

from atpx.blueprint import (
    REQUIREMENTS,
    Blueprint,
    Claim,
    manifest_text,
    register,
    satisfied,
    toml_value,
)

scalars = st.one_of(
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False),
    st.text(),
)
values = st.one_of(
    scalars, st.lists(scalars, max_size=3), st.dictionaries(st.text(), scalars, max_size=3)
)
manifests = st.fixed_dictionaries(
    {"zettel": st.text(), "claims": st.dictionaries(st.text(), values, max_size=4)}
)


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


def test_a_malformed_claims_table_is_a_clean_error(root: Path) -> None:
    directory = root / "research" / "math" / "broken"
    directory.mkdir()
    (directory / "atpx.toml").write_text('zettel = "B"\nclaims = 5\n')
    with pytest.raises(ValueError, match="claims"):
        Blueprint.load(directory)


def test_satisfied_probes_the_requirement_vocabulary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: True)
    assert satisfied("cuda")
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: False)
    assert not satisfied("cuda")
    with pytest.raises(KeyError, match="unknown requirement 'quantum'"):
        satisfied("quantum")


def test_register_preserves_claim_tables_on_rewrite(root: Path) -> None:
    blueprints = root / "research" / "math"
    register(blueprints, "demo", "extra", ["echo", "hi"])
    manifest = tomllib.loads((blueprints / "demo" / "atpx.toml").read_text())
    assert manifest["claims"]["extra"] == "echo hi"
    assert manifest["claims"]["gpu"] == {
        "command": "python {dir}/checks.py gpu",
        "requires": "cuda",
    }


def test_register_without_a_command_creates_an_empty_manifest(root: Path) -> None:
    blueprints = root / "research" / "math"
    blueprint = register(blueprints, "greenfield", "lean")
    assert blueprint.claims == {}
    assert tomllib.loads((blueprints / "greenfield" / "atpx.toml").read_text()) == {
        "zettel": "greenfield",
        "claims": {},
    }


def test_register_refuses_path_segments_in_slugs_and_claims(root: Path) -> None:
    blueprints = root / "research" / "math"
    with pytest.raises(ValueError, match="single path segments"):
        register(blueprints, "a/b", "ok")
    with pytest.raises(ValueError, match="single path segments"):
        register(blueprints, "demo", "a/b")


def test_register_tolerates_a_malformed_claims_scalar(root: Path) -> None:
    """A manifest whose `claims` is not a table registers nothing and fails on load."""
    directory = root / "research" / "math" / "broken"
    directory.mkdir()
    (directory / "atpx.toml").write_text('zettel = "B"\nclaims = 5\n')
    with pytest.raises(ValueError, match="claims"):
        register(root / "research" / "math", "broken", "probe", ["echo", "hi"])
    assert tomllib.loads((directory / "atpx.toml").read_text())["claims"] == 5


@given(manifests)
def test_manifest_text_round_trips_through_tomllib(recorded: dict[str, JsonValue]) -> None:
    assert tomllib.loads(manifest_text(recorded)) == recorded


def test_manifest_text_quotes_hostile_keys_and_values() -> None:
    recorded: dict[str, JsonValue] = {
        "zettel": 'a "quoted" \\ backslash',
        "claims": {"needs quoting": "echo \x7f", "": {"command": "c\nd"}},
    }
    assert tomllib.loads(manifest_text(recorded)) == recorded


def test_manifest_text_inlines_tables_below_the_claim_level() -> None:
    recorded: dict[str, JsonValue] = {
        "zettel": "deep",
        "claims": {"probe": {"command": "c", "meta": {"inner key": ["x", 1.5, True]}}},
    }
    assert tomllib.loads(manifest_text(recorded)) == recorded


def test_toml_value_refuses_what_toml_cannot_hold() -> None:
    with pytest.raises(ValueError, match="TOML cannot hold"):
        toml_value(None)

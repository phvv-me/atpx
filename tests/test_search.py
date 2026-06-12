import json
import stat
from pathlib import Path

import httpx
import pytest
import respx

from atpx.engines import (
    ArxivEngine,
    Capability,
    Engine,
    LoogleEngine,
    OeisEngine,
    SearchError,
    VaultEngine,
    ZbmathEngine,
)

ATOM_FEED = """<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2602.01657v1</id>
    <title>List Decoding of the
      Leech Lattice</title>
  </entry>
</feed>
"""


def test_search_engines_enroll_behind_the_vault() -> None:
    names = [engine().name for engine in Engine.supporting(Capability.SEARCH)]
    assert names == ["vault", "oeis", "loogle", "arxiv", "zbmath"]


def test_search_engines_stamp_atpx_own_version() -> None:
    assert OeisEngine().version() == VaultEngine().version()
    assert OeisEngine().available()


@pytest.fixture
def fake_chefe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake chefe on PATH whose behavior the body file controls."""
    monkeypatch.setenv("PATH", str(tmp_path))
    return tmp_path / "chefe"


def chefe_script(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_vault_engine_shapes_qmd_hits(fake_chefe: Path, tmp_path: Path) -> None:
    reply = [{"file": "qmd://zettel/A.md", "title": "A", "score": 0.9, "snippet": "..."}]
    chefe_script(fake_chefe, f"echo '{json.dumps(reply)}'")
    hits = json.loads(VaultEngine(tmp_path).run("search", "leech"))
    assert hits == [{"id": "qmd://zettel/A.md", "title": "A", "score": 0.9, "snippet": "..."}]


def test_vault_engine_runs_chefe_from_its_root(fake_chefe: Path, tmp_path: Path) -> None:
    record = 'pwd | sed \'s|.*|[{"file":"&","title":"","score":0,"snippet":""}]|\''
    chefe_script(fake_chefe, record)
    hits = json.loads(VaultEngine(tmp_path).run("search", "anything"))
    assert hits[0]["id"] == str(tmp_path.resolve())
    assert VaultEngine().cwd == Path.cwd()


def test_vault_engine_raises_on_a_failing_qmd(fake_chefe: Path, tmp_path: Path) -> None:
    chefe_script(fake_chefe, "echo broken >&2; exit 3")
    with pytest.raises(SearchError, match="qmd exited 3: broken"):
        VaultEngine(tmp_path).run("search", "leech")


def test_vault_engine_raises_on_non_json_output(fake_chefe: Path, tmp_path: Path) -> None:
    chefe_script(fake_chefe, "echo No results found")
    with pytest.raises(SearchError, match="printed no JSON"):
        VaultEngine(tmp_path).run("search", "leech")


def test_vault_engine_is_unavailable_without_chefe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    engine = VaultEngine(tmp_path)
    assert not engine.available()
    assert engine.resolved() == "chefe"


@respx.mock
def test_oeis_finds_a_sequence_by_its_values() -> None:
    respx.get("https://oeis.org/search").respond(
        json=[{"number": 8408, "name": "Theta series of Leech lattice.", "data": "1,0,196560"}]
    )
    hits = json.loads(OeisEngine().run("search", "196560, 16773120"))
    assert hits == [
        {
            "id": "A008408",
            "title": "Theta series of Leech lattice.",
            "url": "https://oeis.org/A008408",
        }
    ]


@respx.mock
def test_oeis_reads_the_wrapped_and_empty_reply_shapes() -> None:
    respx.get("https://oeis.org/search").respond(
        json={"results": [{"number": 2, "name": "n."}], "count": 1}
    )
    assert json.loads(OeisEngine().run("search", "1,2"))[0]["id"] == "A000002"
    respx.get("https://oeis.org/search").respond(json={"results": None, "count": 0})
    assert json.loads(OeisEngine().run("search", "definitely nothing")) == []


@respx.mock
def test_loogle_shapes_declaration_hits() -> None:
    respx.get("https://loogle.lean-lang.org/json").respond(
        json={"hits": [{"name": "Real.sqrt", "type": "Real -> Real", "module": "Mathlib.X"}]}
    )
    hits = json.loads(LoogleEngine().run("search", "Real.sqrt"))
    assert hits == [{"id": "Real.sqrt", "title": "Real -> Real", "module": "Mathlib.X"}]
    respx.get("https://loogle.lean-lang.org/json").respond(json={"count": 0})
    assert json.loads(LoogleEngine().run("search", "nothing")) == []


@respx.mock
def test_loogle_surfaces_query_errors() -> None:
    respx.get("https://loogle.lean-lang.org/json").respond(json={"error": "unknown identifier"})
    with pytest.raises(SearchError, match="unknown identifier"):
        LoogleEngine().run("search", "bad(((")


@respx.mock
def test_arxiv_parses_the_atom_feed() -> None:
    respx.get("https://export.arxiv.org/api/query").respond(text=ATOM_FEED)
    hits = json.loads(ArxivEngine().run("search", "Leech lattice"))
    assert hits == [
        {"id": "http://arxiv.org/abs/2602.01657v1", "title": "List Decoding of the Leech Lattice"}
    ]


@respx.mock
def test_arxiv_raises_on_a_broken_feed() -> None:
    respx.get("https://export.arxiv.org/api/query").respond(text="<feed><unclosed>")
    with pytest.raises(SearchError, match="arxiv"):
        ArxivEngine().run("search", "anything")


@respx.mock
def test_zbmath_shapes_document_hits() -> None:
    respx.get("https://api.zbmath.org/v1/document/_search").respond(
        json={
            "result": [
                {
                    "identifier": "0176.51603",
                    "zbmath_url": "https://zbmath.org/3282426",
                    "title": {"title": "Six and seven dimensional non-lattice sphere packings"},
                },
                {"identifier": "0001.00001", "zbmath_url": None, "title": {"title": "Untitled"}},
            ]
        }
    )
    hits = json.loads(ZbmathEngine().run("search", "Leech lattice"))
    assert hits[0]["id"] == "https://zbmath.org/3282426"
    assert hits[1]["id"] == "0001.00001"


@respx.mock
def test_network_failures_become_search_errors() -> None:
    respx.get("https://oeis.org/search").respond(status_code=503)
    with pytest.raises(SearchError, match="oeis"):
        OeisEngine().run("search", "1,2,3")
    respx.get("https://api.zbmath.org/v1/document/_search").mock(
        side_effect=httpx.ConnectTimeout("timed out")
    )
    with pytest.raises(SearchError, match="zbmath"):
        ZbmathEngine().run("search", "anything")


@respx.mock
def test_an_unreadable_reply_becomes_a_search_error() -> None:
    respx.get("https://oeis.org/search").respond(json=[{"name": "missing number"}])
    with pytest.raises(SearchError, match="oeis.*number"):
        OeisEngine().run("search", "1,2,3")


@pytest.mark.integration
def test_live_oeis_finds_the_leech_theta_series() -> None:
    hits = json.loads(OeisEngine().run("search", "196560, 16773120"))
    assert any(hit["id"] == "A008408" for hit in hits)

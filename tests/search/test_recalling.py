import pytest

from atpx import Capability, Engine, SearchError, Workspace
from atpx.engines import EngineUnavailableError, OeisEngine, UnsupportedOperationError

from ..support import fetcher, result_of


def test_recall_certifies_hits_per_source(
    space: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(OeisEngine, "fetch", fetcher("oeis"))
    certificate = space.sync.recall("196560, 16773120", sources=["oeis"])
    assert certificate.ok
    assert result_of(certificate)["hits"]["oeis"][0]["id"] == "oeis-1"


def test_recall_records_failures_and_exits_nonzero(
    space: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(engine: OeisEngine, payload: str) -> str:
        raise SearchError("oeis is down")

    monkeypatch.setattr(OeisEngine, "fetch", failing)
    certificate = space.sync.recall("anything", sources=["oeis"])
    assert not certificate.ok and "oeis is down" in result_of(certificate)["errors"]["oeis"]


def test_recall_reports_unavailable_sources(
    space: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(OeisEngine, "available", lambda engine: False)
    certificate = space.sync.recall("query", sources=["oeis"])
    assert not certificate.ok and "oeis" in result_of(certificate)["errors"]


def test_recall_defaults_to_every_search_engine(
    space: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    roster = Engine.supporting(Capability.SEARCH)
    for engine in roster:
        monkeypatch.setattr(engine, "fetch", fetcher(engine().name))
    certificate = space.sync.recall("anything")
    assert certificate.ok
    assert sorted(result_of(certificate)["hits"]) == sorted(one().name for one in roster)


def test_recall_refuses_engines_that_cannot_search(
    space: Workspace, ghost_engine: type[Engine]
) -> None:
    with pytest.raises(UnsupportedOperationError, match="ghost"):
        space.sync.recall("query", sources=["ghost"])


def test_an_absent_engine_reports_itself_honestly(ghost_engine: type[Engine]) -> None:
    ghost = ghost_engine()
    assert not ghost.available()
    assert ghost.version() == "unknown"
    with pytest.raises(EngineUnavailableError, match="ghost"):
        ghost.ensure_available()

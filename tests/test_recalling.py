import pytest

from atpx.engines import (
    Capability,
    Engine,
    EngineUnavailableError,
    OeisEngine,
    SearchError,
    UnsupportedOperationError,
    VaultEngine,
)
from atpx.recalling import Recall
from atpx.workspace import Workspace

from .conftest import FakeRunner, fetcher, result_of


def test_recall_certifies_hits_per_source(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    monkeypatch.setattr(OeisEngine, "fetch", fetcher("oeis"))
    certificate = space.sync.recall("196560, 16773120", sources=["oeis"])
    assert certificate.ok
    assert result_of(certificate)["hits"]["oeis"][0]["id"] == "oeis-1"


def test_recall_records_failures_and_exits_nonzero(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws

    async def failing(engine: OeisEngine, payload: str) -> str:
        raise SearchError("oeis is down")

    monkeypatch.setattr(OeisEngine, "fetch", failing)
    certificate = space.sync.recall("anything", sources=["oeis"])
    assert not certificate.ok and "oeis is down" in result_of(certificate)["errors"]["oeis"]


def test_recall_reports_unavailable_sources(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    monkeypatch.setattr(VaultEngine, "available", lambda engine: False)
    certificate = space.sync.recall("query", sources=["vault"])
    assert not certificate.ok and "vault" in result_of(certificate)["errors"]


def test_selected_defaults_to_every_search_engine(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, runner = ws
    assert Recall(space.root).selected(None) == Engine.supporting(Capability.SEARCH)


def test_source_refuses_engines_that_cannot_search(
    ws: tuple[Workspace, FakeRunner], ghost_engine: type[Engine]
) -> None:
    space, runner = ws
    with pytest.raises(UnsupportedOperationError, match="ghost"):
        Recall(space.root).source(ghost_engine)


def test_an_absent_engine_reports_itself_honestly(ghost_engine: type[Engine]) -> None:
    ghost = ghost_engine()
    assert not ghost.available()
    assert ghost.version() == "unknown"
    with pytest.raises(EngineUnavailableError, match="ghost"):
        ghost.ensure_available()

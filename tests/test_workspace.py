import asyncio
import json
import tomllib
from pathlib import Path

import pytest

from atpx.blueprint import REQUIREMENTS
from atpx.evidence import EvidenceStore
from atpx.roles import Status
from atpx.workspace import Workspace, find_root, workspace

from .conftest import FakeRunner, evidence_entries, result_of, stamped, zettel_text


def test_find_root_walks_past_blueprint_manifests(root: Path) -> None:
    inner = root / "research" / "math" / "demo"
    assert find_root(inner) == root


def test_find_root_fails_loudly_outside_a_workspace(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no atpx.toml"):
        find_root(tmp_path)


def test_find_root_honors_the_environment_override(
    root: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("ATPX_ROOT", str(root))
    assert find_root() == root
    assert workspace().root == root


def test_find_root_rejects_a_pinned_non_workspace(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path_factory.mktemp("not-a-workspace")
    monkeypatch.setenv("ATPX_ROOT", str(elsewhere))
    with pytest.raises(FileNotFoundError, match="ATPX_ROOT"):
        find_root()


def test_an_explicit_start_beats_the_environment_override(
    root: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ATPX_ROOT", str(root))
    with pytest.raises(FileNotFoundError, match="no atpx.toml"):
        find_root(tmp_path_factory.mktemp("named-start"))


def test_workspace_discovers_root_from_the_cwd(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(root / "research")
    assert workspace().root == root


def test_check_stamps_and_persists_evidence(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    certificate = space.sync.check("demo", "ok", seed=7)
    assert certificate.ok and certificate.seed == 7
    assert certificate.claim == "demo/ok"
    assert runner.calls == [["python", "research/math/demo/checks.py", "ok"]]
    (entry,) = evidence_entries(space.blueprints / "demo")
    assert entry["claim"] == "demo/ok"


def test_check_records_failures_too(root: Path) -> None:
    space = Workspace(root, runner=FakeRunner(exit_status=3, output="boom\n"))
    certificate = space.sync.check("demo", "ok")
    assert not certificate.ok and certificate.exit_status == 3


def test_check_skips_claims_this_host_cannot_run(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: False)
    certificate = space.sync.check("demo", "gpu")
    assert certificate.ok and certificate.result == {"skipped": True, "requires": "cuda"}
    assert runner.calls == [] and evidence_entries(space.blueprints / "demo") == []


def test_check_runs_required_claims_when_the_host_qualifies(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: True)
    assert space.sync.check("demo", "gpu").ok and len(runner.calls) == 1


def test_run_auto_registers_and_persists(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    certificate = space.sync.run("fresh", "probe", "python", "-c", "print(1)")
    assert certificate.ok and certificate.claim == "fresh/probe"
    manifest = tomllib.loads((space.blueprints / "fresh" / "atpx.toml").read_text())
    assert manifest["zettel"] == "fresh"
    assert manifest["claims"]["probe"] == "python -c 'print(1)'"
    (entry,) = evidence_entries(space.blueprints / "fresh")
    assert entry["claim"] == "fresh/probe"


def test_run_keeps_the_first_recorded_command(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    space.sync.run("fresh", "probe", "python", "-c", "print(1)")
    space.sync.run("fresh", "probe", "python", "-c", "print(2)")
    manifest = tomllib.loads((space.blueprints / "fresh" / "atpx.toml").read_text())
    assert manifest["claims"]["probe"] == "python -c 'print(1)'"


def test_run_replays_a_registered_claim_without_a_command(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, runner = ws
    certificate = space.sync.run("demo", "ok")
    assert certificate.ok
    assert runner.calls == [["python", "research/math/demo/checks.py", "ok"]]


class SleepyRunner:
    """A runner that outlives any reasonable timeout."""

    async def __call__(self, argv: list[str]) -> tuple[int, str]:
        await asyncio.sleep(60)
        return 0, "never"


def test_run_enforces_the_hard_timeout(root: Path) -> None:
    space = Workspace(root, runner=SleepyRunner())
    certificate = space.sync.run("demo", "ok", timeout=0.01)
    assert certificate.exit_status == 124


def test_status_groups_by_ladder_with_an_invalid_bucket(root: Path) -> None:
    vault = root / "vault" / "Zettelkasten"
    (vault / "Odd.md").write_text(
        zettel_text("open", title="Odd").replace("status: open", "status: theorem-retracted")
    )
    space = Workspace(root, runner=FakeRunner())
    groups = space.status()
    assert "Demo Node" in groups["open"] and "Dep" in groups["sketched"]
    assert groups["invalid"] == ["Odd (theorem-retracted)"]


def test_graph_lists_the_frontier(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    (ready,) = [entry for entry in space.graph() if entry["node"] == "Demo Node"]
    assert ready["deps"] == {"Dep": "sketched"}


def test_log_appends_a_journal_line(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    line = space.log("Demo Node", "refuter", "numeric", "no counterexample up to 1e6.")
    assert line.startswith("- [refuter/numeric ")
    assert line in (space.vault.path / "Demo Node.md").read_text()


def test_log_refuses_an_entry_that_would_not_round_trip(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, runner = ws
    with pytest.raises(ValueError, match="pattern"):
        space.log("Demo Node", "the refuter", "numeric", "spaces break the who field")
    with pytest.raises(ValueError, match="one line"):
        space.log("Demo Node", "refuter", "numeric", "line one\nline two")


def test_settle_moves_a_free_status_and_journals_it(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    line = space.settle("Demo Node", "in_progress", "picking this up.")
    assert line.startswith("- [settle/in_progress ")
    assert space.vault.find("Demo Node").status is Status.IN_PROGRESS


def test_fit_is_honest_about_a_dormant_lane_and_never_persists_it(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, runner = ws
    certificate = space.fit("data.csv", "distortion", slug="demo")
    assert certificate.exit_status == 1
    assert "pysr" in json.dumps(certificate.result)
    assert EvidenceStore.ledgers(space.blueprints / "demo") == {}


def test_index_regenerates_and_writes(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    text = space.index(write=True)
    assert "- [[Dep]], a settled dep." in text
    assert text == space.results_index.path.read_text()


def test_index_without_write_leaves_the_file_alone(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    before = space.results_index.path.read_text()
    text = space.index()
    assert "- [[Dep]], a settled dep." in text
    assert space.results_index.path.read_text() == before


def test_sync_facade_refuses_a_running_event_loop(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws

    async def misuse() -> None:
        space.sync.check("demo", "ok")

    with pytest.raises(RuntimeError, match="await the async verb"):
        asyncio.run(misuse())


def test_verify_reruns_runnable_claims_and_flags_stale_evidence(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: False)
    EvidenceStore(root / "research" / "math" / "demo").append(stamped("demo/ok"))
    space = Workspace(root, runner=FakeRunner())
    certificate = space.sync.verify()
    entry = result_of(certificate)["demo"]
    assert entry["ok"] == {"state": "fresh", "stale": True}
    assert entry["gpu"] == {"state": "skipped", "stale": False}


def test_verify_one_slug_reports_failures(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: False)
    space = Workspace(root, runner=FakeRunner(exit_status=1, output="died\n"))
    certificate = space.sync.verify("demo")
    assert not certificate.ok
    assert result_of(certificate)["demo"]["ok"]["state"] == "failed"

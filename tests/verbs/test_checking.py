import tomllib
from pathlib import Path

import pytest

from atpx import EvidenceStore, Workspace

from ..support import FakeRunner, SleepyRunner, evidence_entries, result_of, stamped


def test_check_stamps_and_persists_evidence(space: Workspace, runner: FakeRunner) -> None:
    certificate = space.sync.check("demo", "ok", seed=7)
    assert certificate.ok and certificate.seed == 7
    assert certificate.claim == "demo/ok"
    assert runner.calls == [["python", f"{space.nodes.directory('demo')}/checks.py", "ok"]]
    (entry,) = evidence_entries(space.nodes.directory("demo"))
    assert entry["claim"] == "demo/ok"


def test_check_records_failures_too(root: Path) -> None:
    space = Workspace(root, runner=FakeRunner(exit_status=3, output="boom\n"))
    certificate = space.sync.check("demo", "ok")
    assert not certificate.ok and certificate.exit_status == 3


def test_check_skips_claims_this_host_cannot_run(
    space: Workspace, runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("atpx.blueprint.claim._REQUIREMENTS", {"cuda": lambda: False})
    certificate = space.sync.check("demo", "gpu")
    assert certificate.ok and certificate.result == {"skipped": True, "requires": "cuda"}
    assert runner.calls == [] and evidence_entries(space.nodes.directory("demo")) == []


def test_check_runs_required_claims_when_the_host_qualifies(
    space: Workspace, runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("atpx.blueprint.claim._REQUIREMENTS", {"cuda": lambda: True})
    assert space.sync.check("demo", "gpu").ok and len(runner.calls) == 1


def test_run_auto_registers_and_persists(space: Workspace) -> None:
    certificate = space.sync.run("fresh", "probe", "python", "-c", "print(1)")
    assert certificate.ok and certificate.claim == "fresh/probe"
    manifest = tomllib.loads((space.nodes.directory("fresh") / "atpx.toml").read_text())
    assert manifest == {"claims": {"probe": "python -c 'print(1)'"}}
    (entry,) = evidence_entries(space.nodes.directory("fresh"))
    assert entry["claim"] == "fresh/probe"


def test_run_records_the_latest_command(space: Workspace) -> None:
    """The manifest is a record of the latest run, so a new command replaces a stale scalar."""
    space.sync.run("fresh", "probe", "python", "-c", "print(1)")
    space.sync.run("fresh", "probe", "python", "-c", "print(2)")
    manifest = tomllib.loads((space.nodes.directory("fresh") / "atpx.toml").read_text())
    assert manifest["claims"]["probe"] == "python -c 'print(2)'"


def test_run_replays_a_registered_claim_without_a_command(
    space: Workspace, runner: FakeRunner
) -> None:
    certificate = space.sync.run("demo", "ok")
    assert certificate.ok
    assert runner.calls == [["python", f"{space.nodes.directory('demo')}/checks.py", "ok"]]


def test_run_enforces_the_hard_timeout(root: Path) -> None:
    space = Workspace(root, runner=SleepyRunner())
    certificate = space.sync.run("demo", "ok", timeout=0.01)
    assert certificate.exit_status == 124


def test_verify_reruns_runnable_claims_and_flags_stale_evidence(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("atpx.blueprint.claim._REQUIREMENTS", {"cuda": lambda: False})
    EvidenceStore(root / "research" / "math" / "demo").append(stamped("demo/ok"))
    space = Workspace(root, runner=FakeRunner())
    certificate = space.sync.verify()
    entry = result_of(certificate)["demo"]
    assert entry["ok"] == {"state": "fresh", "stale": True}
    assert entry["gpu"] == {"state": "skipped", "stale": False}


def test_verify_one_slug_reports_failures(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("atpx.blueprint.claim._REQUIREMENTS", {"cuda": lambda: False})
    space = Workspace(root, runner=FakeRunner(exit_status=1, output="died\n"))
    certificate = space.sync.verify("demo")
    assert not certificate.ok
    assert result_of(certificate)["demo"]["ok"]["state"] == "failed"

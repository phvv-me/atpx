import json
import os
import stat
import time
from pathlib import Path

import pytest

from atpx.background import Submission
from atpx.evidence import EvidenceStore
from atpx.workspace import Workspace

from .conftest import FakeRunner, stamped


@pytest.fixture
def fake_chefe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake chefe alone on PATH that echoes its argv into stdout."""
    script = tmp_path / "chefe"
    script.write_text('#!/bin/sh\necho "ran $@"\n')
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(tmp_path))
    return script


def settled(log: Path, timeout: float = 5.0) -> str:
    """The detached child's output once it lands, polling the log file."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if content := log.read_text():
            return content
        time.sleep(0.01)
    raise TimeoutError(f"{log} stayed empty")


def test_background_check_detaches_and_records_the_submission(
    ws: tuple[Workspace, FakeRunner], fake_chefe: Path
) -> None:
    space, runner = ws
    certificate = space.check("demo", "ok", background=True)
    assert runner.calls == []
    result = certificate.result
    assert isinstance(result, dict)
    assert result["detached"] is True and isinstance(result["pid"], int)
    log = space.root / str(result["log"])
    assert "ran run atpx check demo ok" in settled(log)
    records = sorted((space.blueprints / "demo" / "checks").glob("*.json"))
    submission = Submission.model_validate_json(records[0].read_text())
    assert submission.claim == "ok" and submission.pid == result["pid"]


def test_background_check_validates_the_claim_before_detaching(
    ws: tuple[Workspace, FakeRunner], fake_chefe: Path
) -> None:
    space, _ = ws
    with pytest.raises(KeyError, match="known claims"):
        space.check("demo", "missing", background=True)
    assert not (space.blueprints / "demo" / "checks").exists()


def test_checks_reports_pending_then_landed(
    ws: tuple[Workspace, FakeRunner], fake_chefe: Path
) -> None:
    space, _ = ws
    space.check("demo", "ok", background=True)
    (pending,) = space.checks("demo")
    assert pending["claim"] == "ok" and pending["state"] == "pending"
    landed = stamped(claim="demo/ok").model_copy(update={"timestamp": "2099-01-01T00:00:00+00:00"})
    EvidenceStore(space.blueprints / "demo").append(landed)
    (row,) = space.checks("demo")
    assert row["state"] == "landed" and row["submitted"] == pending["submitted"]


def test_checks_ignore_certificates_for_other_claims(
    ws: tuple[Workspace, FakeRunner], fake_chefe: Path
) -> None:
    space, _ = ws
    space.check("demo", "ok", background=True)
    other = stamped(claim="demo/gpu").model_copy(update={"timestamp": "2099-01-01T00:00:00+00:00"})
    EvidenceStore(space.blueprints / "demo").append(other)
    (row,) = space.checks("demo")
    assert row["state"] == "pending"


def test_checks_without_submissions_is_empty(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    assert space.checks("demo") == []


def test_submission_records_are_plain_json(tmp_path: Path) -> None:
    record = Submission(claim="ok", submitted="2026-06-12T00:00:00+00:00", pid=os.getpid())
    parsed = json.loads(record.model_dump_json())
    assert parsed == {"claim": "ok", "submitted": "2026-06-12T00:00:00+00:00", "pid": os.getpid()}

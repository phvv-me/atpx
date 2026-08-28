import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from atpx import EvidenceStore, Workspace
from atpx.background import Submission

from ..support import FakeRunner, stamped


@pytest.fixture
def echoing_atpx(on_path: Callable[[str, str], Path]) -> Path:
    """A fake atpx alone on PATH that echoes its argv into stdout."""
    return on_path("atpx", 'echo "ran $@"')


def settled(log: Path, timeout: float = 5.0) -> str:
    """The detached child's output once it lands, polling the log file."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if content := log.read_text():
            return content
        time.sleep(0.01)
    raise TimeoutError(f"{log} stayed empty")


def test_background_check_detaches_and_records_the_submission(
    space: Workspace, runner: FakeRunner, echoing_atpx: Path
) -> None:
    certificate = space.sync.check("demo", "ok", background=True)
    assert runner.calls == []
    result = certificate.result
    assert isinstance(result, dict)
    assert result["detached"] is True and isinstance(result["pid"], int)
    log = space.root / str(result["log"])
    assert "ran check demo ok" in settled(log)


def test_background_check_writes_the_submission_record(
    space: Workspace, echoing_atpx: Path
) -> None:
    certificate = space.sync.check("demo", "ok", background=True)
    result = certificate.result
    assert isinstance(result, dict)
    records = sorted((space.nodes.directory("demo") / "checks").glob("*.json"))
    submission = Submission.model_validate_json(records[0].read_text())
    assert submission.claim == "ok" and submission.pid == result["pid"]


def test_background_check_validates_the_claim_before_detaching(
    space: Workspace, echoing_atpx: Path
) -> None:
    with pytest.raises(KeyError, match="known claims"):
        space.sync.check("demo", "missing", background=True)
    assert not (space.nodes.directory("demo") / "checks").exists()


def test_checks_reports_pending_then_landed(space: Workspace, echoing_atpx: Path) -> None:
    space.sync.check("demo", "ok", background=True)
    (pending,) = space.checks("demo")
    assert pending["claim"] == "ok" and pending["state"] == "pending"
    future = {"timestamp": "2099-01-01T00:00:00.000000Z"}
    landed = stamped(claim="demo/ok").model_copy(update=future)
    EvidenceStore(space.nodes.directory("demo")).append(landed)
    (row,) = space.checks("demo")
    assert row["state"] == "landed" and row["submitted"] == pending["submitted"]


def test_checks_ignore_certificates_for_other_claims(space: Workspace, echoing_atpx: Path) -> None:
    space.sync.check("demo", "ok", background=True)
    future = {"timestamp": "2099-01-01T00:00:00.000000Z"}
    other = stamped(claim="demo/gpu").model_copy(update=future)
    EvidenceStore(space.nodes.directory("demo")).append(other)
    (row,) = space.checks("demo")
    assert row["state"] == "pending"


def test_checks_never_land_on_a_claim_sharing_a_prefix(
    space: Workspace, echoing_atpx: Path
) -> None:
    """A certificate for `demo/okx` must not land the submission for `ok`."""
    space.sync.check("demo", "ok", background=True)
    shared = stamped(claim="demo/okx").model_copy(
        update={"timestamp": "2099-01-01T00:00:00.000000Z"}
    )
    EvidenceStore(space.nodes.directory("demo")).append(shared)
    (row,) = space.checks("demo")
    assert row["state"] == "pending"


def test_checks_without_submissions_is_empty(space: Workspace) -> None:
    assert space.checks("demo") == []


def test_submission_records_are_plain_json() -> None:
    record = Submission(claim="ok", submitted="2026-06-12T00:00:00.000000Z", pid=os.getpid())
    parsed = json.loads(record.model_dump_json())
    stamp = "2026-06-12T00:00:00.000000Z"
    assert parsed == {"claim": "ok", "submitted": stamp, "pid": os.getpid()}

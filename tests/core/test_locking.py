import subprocess
import sys
from pathlib import Path

import pytest
from filelock import Timeout
from pytest_mock import MockerFixture

from atpx.core.locking import Guard

_CRASH_HOLDING_LOCK = """
import os
import sys
from pathlib import Path

from atpx.core.locking import Guard

with Guard(Path(sys.argv[1])):
    os._exit(77)
"""


class WindowsSharingViolation(PermissionError):
    """The Windows error raised when an open handle denies deletion."""

    winerror = 32


def test_guard_sweeps_after_a_platform_refuses_to_unlink_its_open_handle(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """Model Windows' sharing rule on every platform, then take the released-handle path."""
    guard = Guard(tmp_path / "ledger.ndjson")
    unlink = Path.unlink

    def windows_unlink(path: Path, *, missing_ok: bool = False) -> None:
        if path == guard.file and guard.lock.is_locked:
            raise WindowsSharingViolation
        unlink(path, missing_ok=missing_ok)

    mocker.patch.object(Path, "unlink", windows_unlink)

    with guard:
        assert guard.file.exists()

    assert not guard.file.exists()


def test_guard_leaves_cleanup_to_a_peer_that_keeps_the_file_open(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """A busy pathname is harmless: the active peer owns the next safe sweep."""
    guard = Guard(tmp_path / "ledger.ndjson")
    attempts = 0
    unlink = Path.unlink

    def occupied_unlink(path: Path, *, missing_ok: bool = False) -> None:
        nonlocal attempts
        if path == guard.file:
            attempts += 1
            raise WindowsSharingViolation
        unlink(path, missing_ok=missing_ok)

    mocker.patch.object(Path, "unlink", occupied_unlink)

    with guard:
        assert guard.file.exists()

    assert attempts == 2
    assert guard.file.exists()


def test_guard_propagates_a_real_permission_denial(tmp_path: Path, mocker: MockerFixture) -> None:
    """Only Windows' transient sharing violation is a cleanup race."""
    guard = Guard(tmp_path / "ledger.ndjson")
    unlink = Path.unlink

    def denied_unlink(path: Path, *, missing_ok: bool = False) -> None:
        if path == guard.file and guard.lock.is_locked:
            raise PermissionError
        unlink(path, missing_ok=missing_ok)

    mocker.patch.object(Path, "unlink", denied_unlink)

    with pytest.raises(PermissionError), guard:
        pass


def test_guard_leaves_cleanup_to_a_peer_that_takes_the_lock(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """A peer holding the cleanup lock owns the next sweep."""
    guard = Guard(tmp_path / "ledger.ndjson")

    with guard:
        mocker.patch.object(guard.lock, "acquire", side_effect=Timeout(str(guard.file)))

    assert guard.file.exists()


def test_guard_propagates_a_real_permission_denial_after_releasing_its_handle(
    tmp_path: Path, mocker: MockerFixture
) -> None:
    """A retry suppresses only another Windows sharing violation."""
    guard = Guard(tmp_path / "ledger.ndjson")
    unlink = Path.unlink

    def denied_retry(path: Path, *, missing_ok: bool = False) -> None:
        if path == guard.file and guard.lock.is_locked:
            raise WindowsSharingViolation
        if path == guard.file:
            raise PermissionError
        unlink(path, missing_ok=missing_ok)

    mocker.patch.object(Path, "unlink", denied_retry)

    with pytest.raises(PermissionError), guard:
        pass


def test_guard_recovers_a_lock_path_left_by_a_dead_process(tmp_path: Path) -> None:
    """Kernel ownership dies with the writer and its stale pathname is swept next time."""
    ledger = tmp_path / "ledger.ndjson"
    crashed = subprocess.run(
        [sys.executable, "-c", _CRASH_HOLDING_LOCK, str(ledger)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    lock_file = Path(f"{ledger}.lock")
    assert crashed.returncode == 77
    assert lock_file.exists()
    with Guard(ledger):
        pass
    assert not lock_file.exists()

from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from atpx.core.locking import Guard


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

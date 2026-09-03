from pathlib import Path
from types import TracebackType
from typing import Self

from filelock import FileLock, Timeout

_TIMEOUT = 10.0
_WINDOWS_SHARING_VIOLATION = 32


class Guard:
    """The lock a file-backed ledger takes, whose lock file is swept after use.

    The lock is not the pathname. It lives on a kernel file object and is dropped when its
    process dies, so a session killed mid-write leaves behind a zero-byte `.lock` that blocks
    nobody and that no reader can tell from a live one. Each last holder therefore tries to
    remove the pathname, and the next run also sweeps a crash's leftover instead of letting
    these markers accumulate in a committed workspace.

    POSIX lets the sweep unlink the pathname while holding its kernel lock. Windows denies
    deleting that open file, so the sweep releases its cleanup acquisition and tries once
    more. A peer that wins the intervening race keeps an open handle, makes that deletion
    fail harmlessly, and performs the next sweep when it leaves. Dropping the file on age
    would be unsound: an age-based lease revokes a pathname and never the kernel lock behind
    it, so a waiter could take a fresh inode while a live holder is still writing.
    """

    def __init__(self, path: Path) -> None:
        """path: the file being guarded, whose lock sits beside it as `<path>.lock`."""
        self.file = Path(f"{path}.lock")
        self.lock = FileLock(self.file, timeout=_TIMEOUT, preserve_lock_file=True)

    def __enter__(self) -> Self:
        """Take the lock, re-entrantly for a caller widening it around its own read."""
        self.lock.acquire()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        """Let this holder go, however the block ended, and sweep once the last one has."""
        self.lock.release()
        if not self.lock.is_locked:
            self.__sweep()

    def __sweep(self) -> None:
        """Remove the lock file, leaving alone one a peer took between that release and here."""
        try:
            with self.lock.acquire(blocking=False):
                self.file.unlink(missing_ok=True)
        except Timeout:
            return
        except PermissionError as error:
            if getattr(error, "winerror", None) != _WINDOWS_SHARING_VIOLATION:
                raise
            # Windows cannot unlink the file while FileLock owns its open handle. The
            # context has released that handle before this handler runs. If a peer opens
            # the file first, Windows refuses this attempt too and that peer sweeps later.
            try:
                self.file.unlink(missing_ok=True)
            except PermissionError as peer_error:
                if getattr(peer_error, "winerror", None) != _WINDOWS_SHARING_VIOLATION:
                    raise

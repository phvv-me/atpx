from contextlib import suppress
from pathlib import Path
from types import TracebackType
from typing import Self

from filelock import FileLock, Timeout

_TIMEOUT = 10.0


class Guard:
    """The lock a file-backed ledger takes, whose lock file never outlives its last holder.

    The lock is not the file. It lives on the inode and is held by the kernel, which drops
    it the moment the process holding it dies, so a session killed mid-write leaves behind
    a zero-byte `.lock` that blocks nobody and that no reader can tell from a live one.
    The last holder out therefore removes the pathname, and a crash's leftover is swept by
    the next run that takes the lock, which bounds the litter to one file between a crash
    and the next write instead of letting it accumulate in a committed workspace.

    The sweep runs only while holding the lock it is about to remove, and only when that
    re-take comes free, which is the one moment no peer is inside the critical section.
    Dropping the file on age instead would be unsound: an age-based lease revokes a
    pathname and never the kernel lock behind it, so a waiter would take a fresh inode
    while a live holder is still writing, and two of them would be inside at once.
    """

    def __init__(self, path: Path) -> None:
        """path: the file being guarded, whose lock sits beside it as `<path>.lock`."""
        self.file = Path(f"{path}.lock")
        self.lock = FileLock(self.file, timeout=_TIMEOUT)

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
        with suppress(Timeout), self.lock.acquire(blocking=False):
            self.file.unlink(missing_ok=True)

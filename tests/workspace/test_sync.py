import pytest

from atpx import Workspace
from atpx.support import drive


async def misused(space: Workspace) -> None:
    """Call a blocking sync verb from inside a running loop, which must be refused."""
    space.sync.check("demo", "ok")


def test_sync_facade_refuses_a_running_event_loop(space: Workspace) -> None:
    with pytest.raises(RuntimeError, match="await the async verb"):
        drive(misused(space))

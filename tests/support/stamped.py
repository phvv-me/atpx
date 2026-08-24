from atpx import Certificate
from atpx.core import short_hostname


def stamped(claim: str = "demo/ok", exit_status: int = 0) -> Certificate:
    """A cheap certificate carrying this host's name, no subprocess provenance."""
    return Certificate(
        claim=claim,
        result={"ok": True},
        engine="atpx",
        engine_version="0",
        hostname=short_hostname(),
        device="test",
        git_rev="0000000",
        timestamp="2026-06-12T00:00:00.000000Z",
        exit_status=exit_status,
    )

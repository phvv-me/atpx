from importlib.metadata import version as package_version

from pydantic import JsonValue

from .core.certificate import Certificate
from .running.execution import Running
from .running.payload import clipped
from .support.naming import Naming

_SORRY_MARKER = "sorry"
_RISKY_AXIOMS = ("sorryAx", "ofReduceBool", "ofNat.lit", "Lean.trustCompiler", "native_decide")


class LeanAudit:
    """Turns one Lean build into the certificate `settle verified` demands.

    Lean interaction lives in lean-lsp-mcp; this audit only runs the
    workspace's lean task, counts sorries, and scans the output for the risky
    axiom markers, recording the found subset as `flagged`. Exit is clean only
    when the build passes with zero sorries and nothing flagged.
    """

    def __init__(self, running: Running, task: str) -> None:
        """running: the command execution seam.

        task: the workspace task that runs the Lean build.
        """
        self.running = running
        self.task = task

    async def certified(self, slug: str, target: str | None, timeout: float | None) -> Certificate:
        """Run the build under the wall-clock cap and stamp the audited certificate.

        slug: the blueprint the certificate names.
        target: the build target passed to the lean task, defaulting to none.
        timeout: hard wall-clock cap in seconds.
        """
        argv = [self.task] + ([target] if target else [])
        exit_status, output = await self.running.bounded(argv, timeout)
        sorries = output.count(_SORRY_MARKER)
        flagged: list[JsonValue] = [marker for marker in _RISKY_AXIOMS if marker in output]
        return Certificate.stamp(
            claim=f"{slug}/lean {target or ''}".strip(),
            result={"sorries": sorries, "flagged": flagged, "output": clipped(output.strip())},
            engine="lean",
            engine_version=package_version(Naming.NAME),
            exit_status=exit_status if exit_status else (1 if sorries or flagged else 0),
            rigor="lean",
            root=self.running.root,
        )

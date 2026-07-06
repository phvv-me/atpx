from importlib.metadata import version as package_version

from pydantic import JsonValue

from . import NAME
from .certificate import Certificate
from .running import Running

SORRY_MARKER = "sorry"
RISKY_AXIOMS = ("sorryAx", "ofReduceBool", "ofNat.lit", "Lean.trustCompiler", "native_decide")


class LeanAudit:
    """Turns one Lean build into the certificate `settle verified` demands.

    Lean interaction lives in lean-lsp-mcp; this audit only runs the
    workspace's lean task, counts sorries, and scans the output for the risky
    axiom markers in `RISKY_AXIOMS`, recording the found subset as `flagged`.
    Exit is clean only when the build passes with zero sorries and nothing
    flagged.
    """

    def __init__(self, running: Running, task: str) -> None:
        """running: the command execution seam.

        task: the chefe task that runs the Lean build.
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
        sorries = output.count(SORRY_MARKER)
        flagged: list[JsonValue] = [marker for marker in RISKY_AXIOMS if marker in output]
        return Certificate.stamp(
            claim=f"{slug}/lean {target or ''}".strip(),
            result={"sorries": sorries, "flagged": flagged, "output": output.strip()[-2000:]},
            engine="lean",
            engine_version=package_version(NAME),
            exit_status=exit_status if exit_status else (1 if sorries or flagged else 0),
            root=self.running.root,
        )

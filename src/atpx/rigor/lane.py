from importlib.metadata import version as package_version

from pydantic import JsonValue

from ..blueprint.manifest import Blueprint
from ..core.certificate import Certificate
from ..running.execution import Running
from ..running.payload import clipped
from ..support.naming import Naming
from .audits import Audit, witnesses


class RigorLane:
    """Runs one claim exactly like `run` and stamps its rigor only when the audit passes.

    The stdout gate reads the full output, not the certificate payload, since a
    probe prints one witness line per checked quantity and every line must
    pass. A gated-out run keeps rigor `sampled` and a forced nonzero exit, so
    it can never feed the `validated` settle gate.
    """

    def __init__(self, running: Running, audit: Audit) -> None:
        """running: the command execution seam.

        audit: the stdout gate deciding whether the run earns its rigor.
        """
        self.running = running
        self.audit = audit

    async def certified(
        self,
        blueprint: Blueprint,
        claim: str,
        seed: int | None = None,
        timeout: float | None = None,
    ) -> Certificate:
        """Run the claim, audit its output, and stamp rigor or force the exit nonzero.

        blueprint: the loaded claim manifest.
        claim: the claim name to run.
        seed: RNG seed to record when the probe used one.
        timeout: hard wall-clock cap in seconds.
        """
        exit_status, output = await self.running.bounded(blueprint.command(claim), timeout)
        violation = self.audit.violation(output) if exit_status == 0 else f"exit {exit_status}"
        result: JsonValue = {
            "witnesses": list[JsonValue](witnesses(output, key=self.audit.key)),
            "violation": violation,
            "output": clipped(output.strip()),
        }
        return Certificate.stamp(
            claim=f"{blueprint.slug}/{claim}",
            result=result,
            engine=Naming.NAME,
            engine_version=package_version(Naming.NAME),
            exit_status=exit_status or (1 if violation else 0),
            seed=seed,
            rigor="sampled" if violation else self.audit.rigor,
            root=self.running.root,
        )

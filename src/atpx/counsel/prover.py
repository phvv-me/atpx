from ..models.lane import Message, ModelLane, Schema
from ..models.lanes import Lanes
from .consulting.openrouter import consult
from .consulting.seam import Counselor
from .probing import cap, charge, fielded, judged, recorded, staged, tactics
from .records.attempt import Attempt
from .records.workbench import Workbench

# Measured prompt protocol from the 2026-08 study; the JSON example hint is worth
# +45 points over schema-only prompting.
_CHARGE = "You write rigorous numerical certificate probes."
_HINT = 'Respond with json only, for example {"probe": "import sys\\n..."}'
_SCHEMA: Schema = {
    "type": "object",
    "properties": {"strategy": {"type": "string"}, "probe": {"type": "string"}},
    "required": ["strategy", "probe"],
    "additionalProperties": False,
}


class Prover:
    """Counsel for the affirmative: writes probes until one lands a stamped certificate."""

    def __init__(self, lane: ModelLane | None = None, counselor: Counselor | None = None) -> None:
        """lane: the model lane consulted, the measured prover lane by default.

        counselor: the model seam, the live OpenRouter client by default.
        """
        self.lane = lane or Lanes().prover
        self.counselor = counselor or consult

    def attempt(
        self,
        space: Workbench,
        *,
        slug: str,
        claim: str,
        spec: str,
        repairs: int = 2,
        timeout: float | None = None,
    ) -> Attempt:
        """One prover episode: consult, run the probe as a real claim, repair on failure.

        Every probe executes through `Workspace.run`, so a passing probe lands
        as a genuine stamped certificate in the evidence ledger, and every
        consultation and outcome appends to `attempts/<claim>.jsonl`. Exhausting
        the repair budget returns an honest failed attempt, never an exception.

        space: the workspace the claim runs in.
        slug: the blueprint directory name, created when missing.
        claim: the claim name the certificate stamps.
        spec: the claim specification text the prover receives.
        repairs: repair rounds allowed after the first probe.
        timeout: probe wall-clock cap in seconds, the measured default when None.
        """
        deadline = cap(timeout)
        directory = space.nodes.directory(slug)
        probe_path = directory / "probes" / f"{claim}.py"
        relative = probe_path.relative_to(space.root).as_posix()
        budget = (
            f"Hard cap: the probe process is killed at {deadline:.0f}s wall clock, "
            "engineer the measurement to finish inside it."
        )
        messages: list[Message] = [
            {"role": "system", "content": charge(_CHARGE, lessons=tactics(space.blueprints))},
            {"role": "user", "content": f"{spec}\n\n{budget}\n\n{_HINT}"},
        ]
        violation = ""
        for round_number in range(repairs + 1):
            consultation = self.counselor(messages, _SCHEMA, self.lane, space.root)
            probe = fielded(consultation, "probe")
            violation = (
                judged(
                    probe,
                    staged(space, probe_path, probe, name=slug, claim=claim, timeout=deadline),
                )
                if probe
                else consultation.error or "the reply carried no probe field"
            )
            recorded(
                directory,
                claim,
                {
                    "round": round_number,
                    "consultation": consultation.model_dump(),
                    "violation": violation,
                },
            )
            if not violation:
                return Attempt(
                    slug=slug, claim=claim, passed=True, rounds=round_number + 1, probe=relative
                )
            messages += self.__repair(consultation.content, violation=violation)
        return Attempt(
            slug=slug,
            claim=claim,
            passed=False,
            rounds=repairs + 1,
            probe=relative,
            violation=violation,
        )

    @staticmethod
    def __repair(reply: str, *, violation: str) -> list[Message]:
        """The repair-round exchange: the model's own reply, then what went wrong."""
        return [
            {"role": "assistant", "content": reply},
            {
                "role": "user",
                "content": f"The probe did not pass. {violation}\n"
                "Fix the probe and respond with the same json shape.",
            },
        ]

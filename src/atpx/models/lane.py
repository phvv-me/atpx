from patos import FrozenModel
from pydantic import JsonValue

Message = dict[str, JsonValue]
Schema = dict[str, JsonValue]


class ModelLane(FrozenModel):
    """One consultation lane: the model consulted, its sampling, and its reasoning policy.

    `reasoning` False is the measured protocol ladder that opens with reasoning
    disabled, right for the cheap prover whose sampling was measured that way.
    True leaves reasoning entirely to the provider, right for reasoning-first
    attackers that a forced reasoning-off request lobotomizes; `effort` names
    a provider reasoning effort (`xhigh` for the ceiling rungs) and only
    applies to reasoning lanes. `timeout` and
    `max_tokens` override the measured protocol for lanes whose serving mode
    needs them, pro-compute tiers that think for minutes and bill tens of
    thousands of reasoning tokens; None keeps the measured defaults.
    """

    model: str
    temperature: float | None = None
    top_p: float | None = None
    reasoning: bool = False
    effort: str | None = None
    timeout: float | None = None
    max_tokens: int | None = None

    def sampling(self) -> dict[str, float]:
        """The sampling parameters this lane sets, omitting what it leaves to the provider."""
        pairs = {"temperature": self.temperature, "top_p": self.top_p}
        return {name: value for name, value in pairs.items() if value is not None}

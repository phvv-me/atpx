from collections.abc import Mapping, Sequence

from patos import FrozenModel
from pydantic import JsonValue

from .lane import ModelLane

_V4FLASH = "deepseek/deepseek-v4-flash-0731"
_LUNA = "openai/gpt-5.6-luna"


class Lanes(FrozenModel):
    """The model roster one workspace consults, the measured defaults unless overridden.

    The defaults are experimental results from the 2026-08 protocol study; do
    not retune them.
    """

    prover: ModelLane = ModelLane(model=_V4FLASH, temperature=1.0, top_p=0.95)
    ladder: Sequence[ModelLane] = (
        ModelLane(model=_V4FLASH, temperature=0.9, top_p=0.95),
        ModelLane(model=_V4FLASH, temperature=0.9, top_p=0.95),
        ModelLane(model=_LUNA, reasoning=True),
        ModelLane(model=_LUNA, reasoning=True),
    )

    @classmethod
    def configured(cls, table: Mapping[str, JsonValue]) -> Lanes:
        """Lanes from the root manifest's optional `[models]` table.

        An overriding prover keeps the measured sampling under its new model
        id, while ladder rungs name their models and leave sampling and
        reasoning to each provider, since a cross-family ladder has no shared
        measured point and a forced reasoning-off request lobotomizes
        reasoning-first rungs. One ladder serves both roles: `refute` walks
        it as the boss roster, and rogue campaigns walk it as the player
        generations, so cost decisions live in exactly one place.

        table: the `[models]` table, `prover` a model id and `ladder` a list
            of model ids or lane tables (`{ model, timeout, max_tokens, effort }`).
        """
        measured = cls()
        prover = (
            measured.prover.model_copy(update={"model": str(table["prover"])})
            if "prover" in table
            else measured.prover
        )
        named = table.get("ladder")
        ladder = (
            (*(cls.__rung(entry) for entry in named),)
            if isinstance(named, list)
            else measured.ladder
        )
        return cls(prover=prover, ladder=ladder)

    @staticmethod
    def __rung(entry: JsonValue) -> ModelLane:
        """One ladder rung from a manifest entry, a model id or a lane table.

        A bare string names the model; a table carries per-lane overrides
        (`timeout`, `max_tokens`) for serving modes the measured protocol
        cannot hold, pro-compute tiers foremost. Reasoning stays with the
        provider either way unless the table says otherwise.
        """
        if isinstance(entry, str):
            return ModelLane(model=entry, reasoning=True)
        if isinstance(entry, dict):
            return ModelLane(**{"reasoning": True, **entry})
        raise ValueError(f"a ladder entry is a model id or a lane table, got {entry!r}")

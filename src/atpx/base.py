from functools import cached_property

from pydantic import BaseModel, ConfigDict

IGNORED_TYPES: tuple[type, ...] = (cached_property,)

__all__ = ["FrozenModel", "Model"]


class Model(BaseModel):
    """Mutable model with standard types only."""

    model_config = ConfigDict(ignored_types=IGNORED_TYPES)


class FrozenModel(BaseModel):
    """Immutable model for certificates and records that never mutate after construction."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, ignored_types=IGNORED_TYPES)

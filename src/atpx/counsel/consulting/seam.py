from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from ...models.consultation import Consultation
from ...models.lane import Message, ModelLane, Schema


class Counselor(Protocol):
    """How counsel reaches a model, the one seam tests replace."""

    def __call__(
        self, messages: Sequence[Message], schema: Schema, lane: ModelLane, root: Path
    ) -> Consultation: ...

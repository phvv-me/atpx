from collections.abc import Sequence
from pathlib import Path

from atpx import Consultation, ModelLane
from atpx.models import Message, Schema


class FakeCounsel:
    """Counselor double replying with canned contents, recording every call's messages."""

    def __init__(self, *replies: str) -> None:
        """replies: the reply contents handed out in order, the last one repeating."""
        self.replies = replies
        self.calls: list[list[Message]] = []

    def __call__(
        self, messages: Sequence[Message], schema: Schema, lane: ModelLane, root: Path
    ) -> Consultation:
        self.calls.append(list(messages))
        content = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return Consultation(content=content, model=lane.model, elapsed=0.01)

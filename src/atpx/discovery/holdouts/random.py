from patos import FrozenModel
from pydantic import JsonValue

from ..contracts.frame import Frame


class RandomHoldout(FrozenModel):
    """The default holdout: a seeded random fifth of the rows."""

    seed: int
    fraction: float = 0.2

    def carve(self, frame: Frame) -> tuple[Frame, Frame]:
        """(train, holdout), never letting the holdout round down to zero rows."""
        holdout = frame.sample(n=max(1, round(self.fraction * len(frame))), random_state=self.seed)
        return frame.drop(holdout.index), holdout

    def described(self) -> dict[str, JsonValue]:
        """The split record the certificate carries."""
        return {"mode": "random", "fraction": self.fraction, "driver": None}

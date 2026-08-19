from patos import FrozenModel
from pydantic import JsonValue

from ..contracts.frame import Frame


class TailHoldout(FrozenModel):
    """The extrapolation holdout: the rows with the largest driver values.

    A random split does not predict extrapolation, so this one scores it.
    """

    fraction: float
    driver: str

    def carve(self, frame: Frame) -> tuple[Frame, Frame]:
        """(train, holdout), the holdout being the driver's largest rows."""
        holdout = frame.nlargest(max(1, round(self.fraction * len(frame))), self.driver)
        return frame.drop(holdout.index), holdout

    def described(self) -> dict[str, JsonValue]:
        """The split record the certificate carries."""
        return {"mode": "tail", "fraction": self.fraction, "driver": self.driver}

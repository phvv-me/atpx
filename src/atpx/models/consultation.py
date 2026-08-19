from patos import FrozenModel


class Consultation(FrozenModel):
    """One model call's record: the reply, its token usage, and how long it took."""

    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    elapsed: float
    error: str = ""

    @property
    def ok(self) -> bool:
        """Whether the lane produced a reply."""
        return not self.error

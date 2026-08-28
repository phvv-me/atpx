from patos import FrozenModel
from pydantic import ConfigDict

from .stance import Stance


class Word(FrozenModel):
    """One settled word of a workspace's vocabulary, and how a terminal prints it.

    name: the word itself, a lifecycle status this workspace is willing to settle on
        and the value a trial receipt's settled column carries.
    letter: the single character a progress line prints, the word's initial when empty.
    markup: the terminal markup the word prints under, exactly the mapping pytest's own
        `pytest_report_teststatus` takes.
    stance: what settling on this word does to the prediction behind it.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    letter: str = ""
    markup: dict[str, bool] = {}
    stance: Stance = Stance.NEITHER

    @property
    def mark(self) -> str:
        """The progress character, the declared letter or the word's own initial."""
        return self.letter or self.name[:1].upper()

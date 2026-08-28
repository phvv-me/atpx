from collections.abc import Mapping

from patos import FrozenModel
from pydantic import JsonValue

from ..graph.status import Status
from .stance import Stance
from .word import Word


class Vocabulary(FrozenModel):
    """The settled words a workspace declares, in the order a report prints them.

    A DATA CONTRACT, not an import. atpx owns the lifecycle, so atpx owns the
    declaration: `[vocabulary]` in the workspace manifest names the settled statuses
    this program is willing to settle on, each with the letter and terminal markup a
    progress line prints and the stance it takes on the prediction behind it. A trial
    harness reads that same table out of that same manifest to print its progress line
    and to validate the settled column it stores, so two vocabularies cannot drift
    apart. Nothing here names a harness and no harness is named here; the table is the
    joint.

    An undeclared table means a workspace has not narrowed the ladder and every settled
    status is allowed. A declared one is exact, and `settle` refuses a settled status
    the table leaves out, so a word nobody declared can never quietly reach a receipt
    column nobody reads.

    words: the declared table, in declaration order.
    """

    words: list[Word] = []

    @property
    def names(self) -> list[str]:
        """The declared words in order, which is what a tally and a refusal both list."""
        return [word.name for word in self.words]

    @classmethod
    def declared(cls, table: Mapping[str, JsonValue]) -> Vocabulary:
        """Read the `[vocabulary]` table, refusing a word outside the lifecycle ladder.

        table: the manifest table, one sub-table per word keyed by the word itself.
        """
        settled = [status.value for status in Status if status.is_settled]
        unknown = [name for name in table if name not in settled]
        if unknown:
            raise ValueError(
                f"[vocabulary] declares {', '.join(unknown)}, which "
                f"{'are' if len(unknown) > 1 else 'is'} not a settled status; "
                f"the settled statuses are {', '.join(settled)}"
            )
        declared = [{"name": name, **cls.__fields(row)} for name, row in table.items()]
        return cls(words=[Word.model_validate(word) for word in declared])

    def settles(self, target: Status) -> bool:
        """Whether this workspace is willing to settle a node on `target`.

        An unsettled status is always free, since a vocabulary states what a program
        settles ON rather than which statuses exist, and a workspace declaring nothing
        narrows nothing.

        target: the lifecycle status a settle is moving to.
        """
        return not self.words or not target.is_settled or target.value in self.names

    def stanced(self, stance: Stance) -> list[str]:
        """The declared words taking one stance, so a tally groups without knowing spellings.

        stance: which position to collect, `neither` being every word that decides nothing.
        """
        return [word.name for word in self.words if word.stance is stance]

    @staticmethod
    def __fields(row: JsonValue) -> dict[str, JsonValue]:
        """One word's declared fields, an empty sub-table for a word declared bare."""
        return dict(row) if isinstance(row, dict) else {}

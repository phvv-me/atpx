from collections.abc import Sequence
from pathlib import Path

from ..models.lane import ModelLane
from ..models.lanes import Lanes
from ..support.clock import today
from .bout import Bout, Context
from .consulting.openrouter import consult
from .consulting.seam import Counselor
from .probing import charge, tactics
from .records.arena import Arena
from .records.episode import Episode
from .records.referral import Referral
from .records.workbench import Workbench

# Measured prompt protocol from the 2026-08 study; the hostile verdict framing
# scored 0.79 against 0.42 without it.
_CHARGE = (
    "You are a hostile referee. Your only incentive is to break the claim below. "
    "Attack it with a numerical counterexample probe that exits 0 exactly when it "
    "demonstrates the claim false. Every number your probe prints must be "
    "COMPUTED inside the probe, never hardcoded, a defense probe will re-measure "
    "any quantity you assert and a fictional premise loses the exchange. Rule "
    "FATAL only with a demonstrating counterexample."
)
_REVIEW_SENTENCE = (
    "Mechanical verdict only, semantic review by the mathematician required before settle."
)


class Refuter:
    """Counsel for the negative: a ladder of boss battles whose emitted verdicts are discarded.

    Each roster lane is a rung fought as a `Bout`, cheapest first, and the
    climb stops at the first bout the defense loses, since the node returns
    to the mathematician either way. Settling stays with the mathematician,
    this class never calls `settle`.
    """

    def __init__(
        self,
        lanes: Sequence[ModelLane] | None = None,
        counselor: Counselor | None = None,
        defender: ModelLane | None = None,
    ) -> None:
        """lanes: the ladder walked as the boss roster, the measured one by default.

        counselor: the model seam, the live OpenRouter client by default.
        defender: the lane answering demonstrated attacks, the prover by default.
        """
        self.lanes = list(lanes) if lanes is not None else Lanes().ladder
        self.counselor = counselor or consult
        self.defender = defender or Lanes().prover

    def fanout(
        self,
        space: Workbench,
        slug: str,
        n: int = 4,
        *,
        rounds: int = 3,
        tries: int = 1,
        context: Context = "live",
    ) -> Referral:
        """Climb up to `n` bouts over one node, stopping at the first the defense loses.

        The roster is a cost ladder walked in order, cheapest lane first, so a
        claim a cheap boss breaks never pays for the dear ones, and the dear
        rungs only ever attack survivors. Within each bout the defender
        answers every demonstrated attack with a defense probe, so strawman
        demonstrations die mechanically instead of waiting for review; an
        attack the defense cannot rebut ends the climb as a FATAL candidate.

        space: the workspace the node lives in.
        slug: the blueprint directory name holding the node.
        n: the maximum number of bouts.
        rounds: each boss's attack budget per bout.
        tries: per-move gate-repair budget for each side.
        context: `live` keeps each boss's history, `fresh` restarts per round.
        """
        node = space.nodes.find(slug)
        lessons = tactics(space.blueprints)
        arena = Arena(space, node, summons=charge(_CHARGE, lessons=lessons), lessons=lessons)
        episodes: list[Episode] = []
        beaten = True
        for index in range(n):
            bout = Bout(
                self.lanes[index % len(self.lanes)],
                arena=arena,
                defender=self.defender,
                counselor=self.counselor,
                rounds=rounds,
                tries=tries,
                context=context,
            )
            moves, beaten = bout.fought(rung=index + 1)
            episodes.extend(moves)
            if not beaten:
                break
        verdict = "survived" if beaten else "FATAL candidate"
        draft = self.__drafted(node.directory, slug=slug, verdict=verdict, episodes=episodes)
        return Referral(
            slug=slug,
            verdict=verdict,
            episodes=episodes,
            draft=draft.relative_to(space.root).as_posix(),
        )

    @staticmethod
    def __drafted(
        directory: Path, *, slug: str, verdict: str, episodes: Sequence[Episode]
    ) -> Path:
        """Write the draft judgment for the mathematician, `judgments/draft-<date>.md`.

        directory: the blueprint directory the judgment lands in.
        slug: the node under judgment.
        verdict: the mechanical verdict the ladder computed.
        episodes: every move of every bout, stdout tails included.
        """
        path = directory / "judgments" / f"draft-{today()}.md"
        lines = [f"# Draft judgment for {slug}", "", f"Mechanical verdict {verdict}.", ""]
        for entry in episodes:
            defending = entry.claim.startswith("defend")
            state = (
                ("rebutting" if entry.demonstrated else "not rebutting")
                if defending
                else ("demonstrating" if entry.demonstrated else "not demonstrating")
            )
            lines += [f"## {entry.claim} ({entry.model})", "", f"{state}. {entry.detail}", ""]
            if entry.stdout:
                lines += ["```", entry.stdout, "```", ""]
        lines += [_REVIEW_SENTENCE]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        return path

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
        episodes, beaten, rung = self.__climbed(
            arena, n, rounds=rounds, tries=tries, context=context
        )
        referral = Referral(
            slug=slug,
            verdict="survived" if beaten else "FATAL candidate",
            rung=rung,
            boss=self.lanes[(rung - 1) % len(self.lanes)].model if rung else "",
            episodes=episodes,
            draft="",
        )
        draft = self.__drafted(node.directory, referral)
        return referral.model_copy(update={"draft": draft.relative_to(space.root).as_posix()})

    @staticmethod
    def __drafted(directory: Path, referral: Referral) -> Path:
        """Write the draft judgment for the mathematician, `judgments/draft-<date>.md`.

        The strongest attacking rung heads the draft as a first-class line, so a
        sketch settling on this ruling names what its survival is worth.

        directory: the blueprint directory the judgment lands in.
        referral: the mechanical outcome, its `draft` path not yet filled in.
        """
        path = directory / "judgments" / f"draft-{today()}.md"
        lines = [f"# Draft judgment for {referral.slug}", ""]
        lines += [f"Mechanical verdict {referral.verdict}.", ""]
        if referral.rung:
            lines += [f"Strongest attacking rung {referral.rung} ({referral.boss}).", ""]
        for entry in referral.episodes:
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

    def __climbed(
        self,
        arena: Arena,
        n: int,
        *,
        rounds: int,
        tries: int = 1,
        context: Context = "live",
    ) -> tuple[list[Episode], bool, int]:
        """Fight the ladder, returning (moves, boss_beaten, strongest rung fought).

        arena: the node, workspace, summons and tactics every rung shares.
        n: the maximum number of bouts.
        rounds: each boss's attack budget per bout.
        tries: per-move gate-repair budget for each side.
        context: `live` keeps each boss's history, `fresh` restarts per round.
        """
        episodes: list[Episode] = []
        beaten = True
        rung = 0
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
            rung = index + 1
            moves, beaten = bout.fought(rung=rung)
            episodes.extend(moves)
            if not beaten:
                break
        return episodes, beaten, rung

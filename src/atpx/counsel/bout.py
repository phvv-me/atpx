from typing import Literal

from ..core.certificate import Certificate
from ..graph.node import Node
from ..models.consultation import Consultation
from ..models.lane import Message, ModelLane, Schema
from .consulting.seam import Counselor
from .probing import charge, fielded, judged, recorded, staged, tail, transcript
from .records.episode import Episode
from .records.workbench import Workbench

_HINT = (
    "Respond with json only, for example "
    '{"verdict": "FATAL", "reason": "...", "counterexample_probe": "import sys\\n..."}'
)
_DEFENSE_CHARGE = (
    "You defend the claim below. An attack probe just demonstrated against it. "
    "Reply with a defense probe that exits 0 exactly when it rebuts the attack: "
    "demonstrate that the attack violates a precondition the statement pins, "
    "printing the violated line; or, when the attack HARDCODES quantities "
    "instead of computing them, re-measure those quantities faithfully and "
    "print measured-vs-hardcoded lines exposing the fiction; or re-measure the "
    "attacked configuration and show the claim's prediction holds there. Print "
    "at least three `case=<name> measured=<v> target=<v> diff=<v>` lines and "
    "call sys.exit explicitly. A defense argues only through what it runs and "
    "measures."
)
_DEFENSE_HINT = (
    'Respond with json only, for example {"reason": "...", "defense_probe": "import sys\\n..."}'
)
_SCHEMA: Schema = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string"},
        "reason": {"type": "string"},
        "counterexample_probe": {"type": "string"},
    },
    "required": ["verdict", "reason", "counterexample_probe"],
    "additionalProperties": False,
}
_DEFENSE_SCHEMA: Schema = {
    "type": "object",
    "properties": {
        "reason": {"type": "string"},
        "defense_probe": {"type": "string"},
    },
    "required": ["reason", "defense_probe"],
    "additionalProperties": False,
}

Context = Literal["live", "fresh"]


class Bout:
    """One rung's boss battle: an attacker and a defender exchanging runnable probes.

    Neither side ever argues in prose. Every move is a probe the machine runs
    and gates, so the exchange cannot settle rhetorically: an attack counts
    only as a gate-clean exit-0 counterexample certificate, and a defense
    counts only as a gate-clean exit-0 rebuttal, a precondition audit or a
    faithful re-measurement. Within one move a side may repair a gate-refused
    probe up to `tries` times, seeing its own violations privately, so a
    format fumble never spends a round. A rebutted attacker gets the
    rebuttal's output and must produce a new attack; an undefended
    demonstration ends the bout lost. `context` picks whether the boss keeps
    its whole bout history (`live`) or opens each round from the node alone
    plus the last ruling (`fresh`), the knob the context experiments compare.
    The mathematician reads the whole exchange in the draft judgment.
    """

    def __init__(
        self,
        attacker: ModelLane,
        *,
        defender: ModelLane,
        counselor: Counselor,
        rounds: int,
        tries: int = 1,
        context: Context = "live",
    ) -> None:
        """attacker: the boss lane swinging counterexample probes.

        defender: the prover lane answering demonstrated attacks.
        counselor: the model seam both sides consult through.
        rounds: the attacker's total attack budget for this bout.
        tries: per-move gate-repair budget for each side.
        context: `live` keeps the boss's full bout history, `fresh` restarts
            each round from the node plus the last ruling.
        """
        self.attacker = attacker
        self.defender = defender
        self.counselor = counselor
        self.rounds = rounds
        self.tries = tries
        self.context = context

    def fought(
        self, space: Workbench, node: Node, *, rung: int, summons: str, lessons: str
    ) -> tuple[list[Episode], bool]:
        """Fight one bout to its end, returning (moves, boss_beaten).

        space: the workspace the probes run in.
        node: the node under attack.
        rung: the 1-based ladder position naming the `refute-<rung>-<round>` claims.
        summons: the assembled hostile system message.
        lessons: the tactics text folded into the defense summons.
        """
        self.space = space
        self.node = node
        self.lessons = lessons
        base: list[Message] = [
            {"role": "system", "content": summons},
            {"role": "user", "content": f"{node.text}\n\n{_HINT}"},
        ]
        history = list(base)
        moves: list[Episode] = []
        for round_number in range(1, self.rounds + 1):
            attack, probe = self.__attacked(history, rung=rung, round_number=round_number)
            moves.append(attack)
            if not attack.demonstrated:
                history = self.__advanced(
                    base, history, f"The attack did not count. {attack.detail}"
                )
                continue
            defense = self.__defended(
                probe, stdout=attack.stdout, rung=rung, round_number=round_number
            )
            moves.append(defense)
            if not defense.demonstrated:
                return moves, False
            history = self.__advanced(
                base,
                history,
                f"A defense probe rebutted your attack. Its output:\n{defense.stdout}\n"
                "Produce a NEW attack that survives this rebuttal.",
            )
        return moves, True

    @staticmethod
    def __feedback(body: str) -> Message:
        """One user-role feedback message carrying the machine's ruling back to a side."""
        return {"role": "user", "content": f"{body}\n{_HINT}"}

    def __advanced(
        self, base: list[Message], history: list[Message], ruling: str
    ) -> list[Message]:
        """The boss's messages for the next round, per the bout's context policy."""
        if self.context == "fresh":
            return [*base, self.__feedback(ruling)]
        history.append(self.__feedback(ruling))
        return history

    def __attacked(
        self, history: list[Message], *, rung: int, round_number: int
    ) -> tuple[Episode, str]:
        """One attack move: consult with the bout history, gate, repair up to `tries`."""
        claim = f"refute-{rung}-{round_number}"
        episode, probe = self.__moved(history, schema=_SCHEMA, lane=self.attacker, claim=claim)
        return episode, probe

    def __defended(
        self, attack_probe: str, *, stdout: str, rung: int, round_number: int
    ) -> Episode:
        """One defense move: a fresh exchange answering the demonstrated attack."""
        messages: list[Message] = [
            {"role": "system", "content": charge(_DEFENSE_CHARGE, lessons=self.lessons)},
            {
                "role": "user",
                "content": (
                    f"{self.node.text}\n\nThe demonstrating attack probe:\n"
                    f"```python\n{attack_probe}\n```\n\n"
                    f"Its output:\n{stdout}\n\n{_DEFENSE_HINT}"
                ),
            },
        ]
        episode, _ = self.__moved(
            messages,
            schema=_DEFENSE_SCHEMA,
            lane=self.defender,
            claim=f"defend-{rung}-{round_number}",
        )
        return episode

    def __moved(
        self, messages: list[Message], *, schema: Schema, lane: ModelLane, claim: str
    ) -> tuple[Episode, str]:
        """One side's move: consult, gate, and privately repair gate refusals.

        Every try consults, stages, and stamps through the same claim, so the
        ledger keeps each intermediate certificate while the bout counts only
        the move's final episode.
        """
        field = "defense_probe" if claim.startswith("defend") else "counterexample_probe"
        episode = Episode(claim=claim, model=lane.model, demonstrated=False, detail="unconsulted")
        probe = ""
        for try_number in range(1, self.tries + 1):
            consultation = self.counselor(messages, schema, lane, self.space.root)
            messages.append({"role": "assistant", "content": consultation.content})
            probe = fielded(consultation, field)
            episode = self.__judged(probe, claim=claim, lane=lane, consultation=consultation)
            if episode.demonstrated:
                break
            if try_number < self.tries:
                messages.append(
                    self.__feedback(f"The probe did not count. {episode.detail}\nRepair it.")
                )
        return episode, probe

    def __judged(
        self, probe: str, *, claim: str, lane: ModelLane, consultation: Consultation
    ) -> Episode:
        """Stage one probe as a real claim, gate it, and record the move.

        The absent-probe message follows the claim kind, `refute-*` moves miss
        a counterexample probe and `defend-*` moves miss a defense probe.
        """
        kind = "defense" if claim.startswith("defend") else "counterexample"
        if probe:
            path = self.node.directory / "probes" / f"{claim}.py"
            certificate: Certificate = staged(
                self.space, path, probe, name=self.node.name, claim=claim
            )
            violation = judged(probe, certificate)
            detail = violation or "gate-clean exit 0"
            stdout = tail(transcript(certificate), 800)
        else:
            violation = consultation.error or f"no {kind} probe emitted"
            detail, stdout = violation, ""
        recorded(
            self.node.directory,
            claim,
            {"consultation": consultation.model_dump(), "violation": violation},
        )
        return Episode(
            claim=claim,
            model=lane.model,
            demonstrated=not violation,
            detail=detail,
            stdout=stdout,
        )

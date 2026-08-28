from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import SettleError, Status, Workspace
from atpx.contracts import Stance, Universe, Vocabulary, Word

from ..support import FakeRunner, node_text, planted

_DECLARED = """[workspace]
blueprints = "math"

[vocabulary]
validated = { letter = "V", markup = { green = true }, stance = "confirms" }
refuted = { letter = "R", markup = { red = true }, stance = "refutes" }
known = {}

[universe]
root = "experiments"
axes = ["card", "model"]
probed = ["torch", "numpy"]
samples = 3
"""

_SETTLED = sorted(status.value for status in Status if status.is_settled)


def declaring(root: Path, manifest: str = _DECLARED) -> Workspace:
    """A workspace over one node, declaring whatever manifest it is handed."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "atpx.toml").write_text(manifest)
    planted(root / "math", "demo", text=node_text("open", body="A claim with no links."))
    return Workspace(root, runner=FakeRunner())


@pytest.fixture
def declared(tmp_path: Path) -> Workspace:
    """A workspace declaring both a vocabulary and a universe."""
    return declaring(tmp_path)


def test_the_vocabulary_table_reads_in_declaration_order(declared: Workspace) -> None:
    vocabulary = declared.vocabulary
    assert vocabulary.names == ["validated", "refuted", "known"]
    assert vocabulary.words[0].markup == {"green": True}
    assert vocabulary.stanced(Stance.CONFIRMS) == ["validated"]
    assert vocabulary.stanced(Stance.NEITHER) == ["known"]


def test_a_bare_word_takes_its_own_initial_and_the_neutral_stance(declared: Workspace) -> None:
    """A workspace that never thinks about stance never records a claim it did not make."""
    known = declared.vocabulary.words[-1]
    assert known.mark == "K" and known.stance is Stance.NEITHER and known.markup == {}
    assert Word(name="refuted", letter="R").mark == "R"


def test_a_word_outside_the_lifecycle_ladder_is_refused(tmp_path: Path) -> None:
    manifest = '[workspace]\nblueprints = "math"\n\n[vocabulary]\nheld = {}\n'
    space = declaring(tmp_path, manifest)
    with pytest.raises(ValueError, match="not a settled status"):
        assert space.vocabulary


def test_settle_refuses_a_word_the_workspace_does_not_declare(declared: Workspace) -> None:
    with pytest.raises(SettleError, match="not a word this workspace settles on"):
        declared.settle("demo", "abandoned")


def test_settle_allows_a_declared_word_and_every_unsettled_status(declared: Workspace) -> None:
    assert "in_progress" in declared.settle("demo", "in_progress")
    assert "known" in declared.settle("demo", "known")


def test_an_undeclared_vocabulary_narrows_nothing(tmp_path: Path) -> None:
    space = declaring(tmp_path, '[workspace]\nblueprints = "math"\n')
    assert space.vocabulary.names == []
    assert "abandoned" in space.settle("demo", "abandoned")


def test_the_universe_table_reads_its_declared_layout(declared: Workspace) -> None:
    universe = declared.universe
    assert universe == Universe(
        root="experiments", axes=["card", "model"], probed=["torch", "numpy"], samples=3
    )
    assert universe is not None and universe.evidence == "evidence/receipts"


def test_an_undeclared_universe_is_absent_rather_than_invented(tmp_path: Path) -> None:
    assert declaring(tmp_path, '[workspace]\nblueprints = "math"\n').universe is None


@given(words=st.lists(st.sampled_from(_SETTLED), min_size=1, max_size=6, unique=True))
def test_exactly_the_declared_words_are_the_ones_a_settle_may_reach(words: list[str]) -> None:
    """The contract's whole point: a word nobody declared never reaches a receipt column."""
    vocabulary = Vocabulary.declared(dict.fromkeys(words, {}))
    permitted = [status.value for status in Status if vocabulary.settles(status)]
    unsettled = [status.value for status in Status if not status.is_settled]
    assert sorted(permitted) == sorted(set(words) | set(unsettled))


def test_an_unknown_key_in_a_declared_table_is_refused(tmp_path: Path) -> None:
    """A schema that ignored a typo would let a consumer read a default it never chose."""
    manifest = '[workspace]\nblueprints = "math"\n\n[universe]\nroot = "e"\nsample = 3\n'
    space = declaring(tmp_path, manifest)
    with pytest.raises(ValueError, match="sample"):
        assert space.universe
    table = '[workspace]\nblueprints = "math"\n\n[vocabulary]\nknown = { colour = "red" }\n'
    other = declaring(tmp_path / "other", table)
    with pytest.raises(ValueError, match="colour"):
        assert other.vocabulary

from pathlib import Path

import pytest
from plumbum import local

from atpx.core import Repository


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """A real one-commit git repository holding a node file."""
    git = local["git"]["-C", str(tmp_path)]
    git("init", "-q")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    (tmp_path / "node.md").write_text("first statement\n")
    git("add", "node.md")
    git("commit", "-qm", "first")
    return tmp_path


def revision(root: Path) -> str:
    """The repository's current short revision."""
    return str(local["git"]["-C", str(root)]("rev-parse", "--short", "HEAD")).strip()


def commit(root: Path, text: str) -> None:
    """Rewrite the node and commit the change."""
    git = local["git"]["-C", str(root)]
    (root / "node.md").write_text(text)
    git("commit", "-qam", "revised")


def test_a_node_untouched_since_the_evidence_was_stamped_is_fresh(repository: Path) -> None:
    node = repository / "node.md"
    assert not Repository(repository).moved_since(revision(repository), node)


def test_a_node_rewritten_after_the_evidence_was_stamped_is_stale(repository: Path) -> None:
    stamped_at = revision(repository)
    commit(repository, "second statement\n")
    assert Repository(repository).moved_since(stamped_at, repository / "node.md")


def test_a_commit_touching_another_file_leaves_the_node_fresh(repository: Path) -> None:
    stamped_at = revision(repository)
    git = local["git"]["-C", str(repository)]
    (repository / "notes.md").write_text("unrelated\n")
    git("add", "notes.md")
    git("commit", "-qm", "unrelated")
    assert not Repository(repository).moved_since(stamped_at, repository / "node.md")


def test_a_dirty_stamp_is_read_as_the_commit_it_names(repository: Path) -> None:
    """The `+dirty` flag is provenance about a working tree, never a commit of its own."""
    stamped_at = revision(repository)
    commit(repository, "second statement\n")
    assert Repository(repository).moved_since(f"{stamped_at}+dirty", repository / "node.md")


@pytest.mark.parametrize("recorded", ["", "unknown"])
def test_evidence_that_recorded_no_revision_is_stale(repository: Path, recorded: str) -> None:
    assert Repository(repository).moved_since(recorded, repository / "node.md")


def test_a_revision_this_checkout_cannot_place_raises_no_alarm(repository: Path) -> None:
    """A lint reports what it can act on, and an unplaceable revision is not that."""
    assert not Repository(repository).moved_since("deadbee", repository / "node.md")

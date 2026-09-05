from pathlib import Path

import pytest

from atpx import Status
from atpx.graph.node import Node
from atpx.graph.result import ResultDocument


def written(directory: Path, name: str, text: str) -> Path:
    """Write one file under `directory`, returning its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def test_a_node_with_no_result_note_declares_nothing(tmp_path: Path) -> None:
    node = written(tmp_path / "demo", "node.md", "---\nstatus: open\n---\n\n# Demo\n")
    assert ResultDocument(node).path is None
    assert ResultDocument(node).declared == ""
    assert ResultDocument(node).verdict is None


@pytest.mark.parametrize("name", ["result.md", "results.md"])
def test_either_spelling_of_the_result_note_is_read(tmp_path: Path, name: str) -> None:
    node = written(tmp_path / "demo", "node.md", "---\nstatus: open\n---\n\n# Demo\n")
    written(tmp_path / "demo", name, "# Result\n\nStatus: **validated** on 2026-09-04.\n")
    assert ResultDocument(node).verdict is Status.VALIDATED


def test_the_note_beside_a_second_node_document_is_named_after_it(tmp_path: Path) -> None:
    """One directory, two registrations, two notes, and neither reads the other's verdict."""
    directory = tmp_path / "campaign"
    first = written(directory, "node.md", "---\nstatus: validated\n---\n\n# First\n")
    second = written(directory, "v2-node.md", "---\nstatus: refuted\n---\n\n# Second\n")
    written(directory, "result.md", "Status: validated\n")
    written(directory, "v2-result.md", "Verdict: refuted\n")
    assert ResultDocument(first).verdict is Status.VALIDATED
    assert ResultDocument(second).verdict is Status.REFUTED


def test_prose_naming_a_ladder_word_declares_no_verdict(tmp_path: Path) -> None:
    """Only the declaring line counts, so a write-up cannot contradict its node by accident."""
    node = written(tmp_path / "demo", "node.md", "---\nstatus: open\n---\n\n# Demo\n")
    written(tmp_path / "demo", "result.md", "# Result\n\nThe predecessor was refuted in July.\n")
    assert ResultDocument(node).verdict is None


def test_a_word_outside_the_ladder_reads_as_no_declaration(tmp_path: Path) -> None:
    node = written(tmp_path / "demo", "node.md", "---\nstatus: open\n---\n\n# Demo\n")
    written(tmp_path / "demo", "result.md", "Status: **measured**\n")
    assert ResultDocument(node).declared == "measured"
    assert ResultDocument(node).verdict is None


def test_a_node_reads_the_note_beside_its_own_document(tmp_path: Path) -> None:
    path = written(tmp_path / "demo", "node.md", "---\nstatus: registered\n---\n\n# Demo\n")
    written(tmp_path / "demo", "result.md", "Status: **validated** on 2026-09-04.\n")
    assert Node(path).result.declared == "validated"

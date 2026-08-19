from datetime import UTC, datetime
from pathlib import Path

import pytest

from atpx import Kind, Status, Workspace
from atpx.study import Scaffold

_CLAIM_SPEC = Path("specs") / "claim-spec.md"


def test_open_scaffolds_a_readable_node(space: Workspace) -> None:
    reported = space.open("locking-kernel", kind="theorem")
    assert reported == "research/math/locking-kernel/node.md"
    node = space.nodes.find("locking-kernel")
    assert node.status is Status.OPEN
    assert node.frontmatter["kind"] == "theorem"
    assert node.frontmatter["date"] == datetime.now(UTC).date().isoformat()
    assert node.frontmatter["references"] == "[]"


@pytest.mark.parametrize("heading", ["## Statement", "## Proof", "## Evidence", "## Log"])
def test_open_templates_every_node_section(space: Workspace, heading: str) -> None:
    space.open("locking-kernel", kind="theorem")
    assert heading in space.nodes.find("locking-kernel").text


def test_open_scaffolds_probes_manifest_and_the_claim_spec(space: Workspace) -> None:
    space.open("locking-kernel", kind="lemma")
    directory = space.blueprints / "locking-kernel"
    assert (directory / "probes").is_dir()
    assert (directory / "atpx.toml").read_text() == "[claims]\n"
    spec = (directory / _CLAIM_SPEC).read_text()
    assert "Feasibility check: reference computation performed? Y/N + numbers" in spec


@pytest.mark.parametrize(
    "heading", ["## Claim", "## Tolerances", "## Emulation hints", "## Exit contract"]
)
def test_open_templates_every_spec_section(space: Workspace, heading: str) -> None:
    space.open("locking-kernel", kind="lemma")
    spec = (space.blueprints / "locking-kernel" / _CLAIM_SPEC).read_text()
    assert heading in spec


def test_open_refuses_to_overwrite_an_existing_node(space: Workspace) -> None:
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        space.open("demo", kind="lemma")


def test_open_rejects_an_unknown_kind(space: Workspace) -> None:
    with pytest.raises(ValueError, match="Kind"):
        space.open("fresh", kind="conjecture")


def test_open_slugifies_a_free_text_title(space: Workspace) -> None:
    reported = space.open("Bijectivity of the E8 Lattice!", kind="theorem")
    assert reported == "research/math/bijectivity-of-the-e8-lattice/node.md"


def test_open_refuses_a_title_that_slugifies_to_nothing(space: Workspace) -> None:
    with pytest.raises(ValueError, match="slugifies to nothing"):
        space.open("???", kind="lemma")


def test_scaffold_rejects_a_slug_with_a_slash(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="single path segments"):
        Scaffold(tmp_path).open("a/b", Kind.LEMMA)


def test_scaffold_keeps_an_existing_manifest_and_spec(tmp_path: Path) -> None:
    directory = tmp_path / "kept"
    (directory / "specs").mkdir(parents=True)
    (directory / "atpx.toml").write_text('[claims]\nok = "true"\n')
    (directory / _CLAIM_SPEC).write_text("handwritten\n")
    Scaffold(tmp_path).open("kept", Kind.EXPERIMENT)
    assert "ok" in (directory / "atpx.toml").read_text()
    assert (directory / _CLAIM_SPEC).read_text() == "handwritten\n"

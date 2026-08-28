import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import NodeStore, Workspace

from ..support import FakeRunner, node_text, planted

_MIGRATED = ("accuracy-selection", "x-structure", "fprev-recovery")


def migrated(root: Path) -> Workspace:
    """A two-root workspace shaped like the reproducibility repo after its migration.

    `math/<kebab>` holds the stubs a migration left behind, each carrying
    `superseded_by: experiments/<snake>`, and `experiments/<snake>` holds the node of
    record, one of which calls its readings `## Ledger` rather than `## Evidence`.
    """
    (root / "atpx.toml").write_text(
        '[workspace]\nblueprints = ["math", "experiments"]\nindex = "math/INDEX.md"\n'
    )
    for index, kebab in enumerate(_MIGRATED):
        snake = kebab.replace("-", "_")
        planted(
            root / "math",
            kebab,
            text=node_text(
                "validated",
                title=kebab,
                summary=f"superseded claim {kebab}",
                body=f"SUPERSEDED, the node of record is `experiments/{snake}`.",
                front={"superseded_by": f"experiments/{snake}"},
            ),
        )
        planted(
            root / "experiments",
            snake,
            text=node_text(
                "validated",
                title=snake,
                summary=f"live claim {snake}",
                body=f"The node of record for {kebab}.",
                heading="## Ledger" if index == 0 else "## Evidence",
            ),
        )
    return Workspace(root, runner=FakeRunner())


@pytest.fixture
def two_roots(tmp_path: Path) -> Workspace:
    """The migrated two-root workspace, over a throwaway root."""
    return migrated(tmp_path)


def test_a_declared_list_of_roots_is_read_as_one_graph(two_roots: Workspace) -> None:
    assert list(two_roots.blueprints) == [two_roots.root / "math", two_roots.root / "experiments"]
    found = {node.name for node in two_roots.nodes.nodes()}
    assert found == set(_MIGRATED) | {slug.replace("-", "_") for slug in _MIGRATED}


def test_a_declared_string_still_names_one_root(root: Path) -> None:
    """The single-root spelling every existing workspace uses keeps working unchanged."""
    space = Workspace(root, runner=FakeRunner())
    assert list(space.blueprints) == [root / "research" / "math"]


def test_a_superseded_claim_is_counted_once_at_its_node_of_record(two_roots: Workspace) -> None:
    assert two_roots.status() == {
        "validated": sorted(slug.replace("-", "_") for slug in _MIGRATED)
    }
    assert two_roots.nodes.aliases() == {
        kebab: f"experiments/{kebab.replace('-', '_')}" for kebab in _MIGRATED
    }


def test_the_index_lists_each_claim_once_and_names_the_root_it_came_from(
    two_roots: Workspace,
) -> None:
    text = two_roots.index()
    graph = json.loads(two_roots.ledger_index.graph_path.read_text())
    assert [row["slug"] for row in graph["nodes"]] == sorted(
        slug.replace("-", "_") for slug in _MIGRATED
    )
    assert {row["root"] for row in graph["nodes"]} == {"experiments"}
    assert all(f"[[{kebab}]]" not in text for kebab in _MIGRATED)


def test_a_ledger_section_takes_a_note_exactly_like_an_evidence_section(
    two_roots: Workspace,
) -> None:
    line = two_roots.note("accuracy_selection", "the reading landed")
    text = (two_roots.nodes.directory("accuracy_selection") / "node.md").read_text()
    assert "## Ledger" in text and text.index("## Ledger") < text.index(line)


def test_a_note_on_a_superseded_node_is_refused_naming_the_node_of_record(
    two_roots: Workspace,
) -> None:
    with pytest.raises(ValueError, match="superseded by experiments/x_structure"):
        two_roots.note("x-structure", "the reading landed")


def test_doctor_reports_the_aliases_and_holds_the_pointers_to_a_real_blueprint(
    two_roots: Workspace,
) -> None:
    report = two_roots.doctor().result
    assert isinstance(report, dict)
    workspaces = report["workspaces"]
    assert isinstance(workspaces, dict)
    here = workspaces["."]
    assert isinstance(here, dict)
    assert here["superseded_nodes"] == two_roots.nodes.aliases()
    assert here["dangling_links"] == {}


def test_a_supersession_pointing_nowhere_is_a_dangling_link(two_roots: Workspace) -> None:
    stub = two_roots.nodes.directory("x-structure") / "node.md"
    stub.write_text(stub.read_text().replace("experiments/x_structure", "experiments/gone"))
    report = two_roots.doctor().result
    assert isinstance(report, dict)
    assert "dangling_links" in str(report["breakages"])


def test_a_dependency_on_a_superseded_slug_resolves_through_the_alias(
    two_roots: Workspace,
) -> None:
    """A wikilink written before the migration still reaches the claim it meant."""
    planted(
        two_roots.root / "experiments",
        "later",
        text=node_text("open", title="later", body="Leans on [[x-structure]]."),
    )
    reached = two_roots.nodes.resolved()["x-structure"]
    assert reached.name == "x_structure" and reached.root == "experiments"
    (row,) = [entry for entry in two_roots.graph() if entry["node"] == "later"]
    assert row["deps"] == {"x-structure": "validated"}


def test_a_run_lands_in_the_root_already_holding_the_slug(two_roots: Workspace) -> None:
    two_roots.sync.run("x_structure", "replay", "python", "probe.py")
    assert (two_roots.root / "experiments" / "x_structure" / "evidence").is_dir()
    assert not (two_roots.root / "math" / "x_structure").exists()


@given(
    kebabs=st.lists(
        st.from_regex(r"claim-[a-z]{1,6}", fullmatch=True), min_size=1, max_size=5, unique=True
    )
)
def test_every_claim_is_counted_exactly_once_however_many_roots_hold_it(
    kebabs: Sequence[str], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """The supersession invariant: one claim, one count, always at its node of record."""
    root = tmp_path_factory.mktemp("supersession")
    for kebab in kebabs:
        snake = kebab.replace("-", "_")
        alone = "A claim with no links at all."
        planted(
            root / "old",
            kebab,
            text=node_text("validated", body=alone, front={"superseded_by": snake}),
        )
        planted(root / "new", snake, text=node_text("open", body=alone))
    store = NodeStore(root / "old", root / "new")
    counted = [node.name for node in store.canonical()]
    assert sorted(counted) == sorted(kebab.replace("-", "_") for kebab in kebabs)
    assert len(store.nodes()) == 2 * len(kebabs)

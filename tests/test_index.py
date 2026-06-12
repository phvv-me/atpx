import tempfile
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from atpx.index import ResultsIndex
from atpx.roles import Status
from atpx.zettel import Vault, Zettel

from .conftest import zettel_text

HEADINGS = {
    Status.VERIFIED: "## Verified (Lean-checked)",
    Status.SKETCHED: "## Sketched (refuter-survived, usable)",
    Status.IN_PROGRESS: "## In progress / open",
    Status.OPEN: "## In progress / open",
    Status.REFUTED: "## Refuted",
    Status.ABANDONED: "## Abandoned",
}

nodes_strategy = st.dictionaries(
    keys=st.from_regex(r"Node [A-Z][a-z]{1,8}", fullmatch=True),
    values=st.tuples(
        st.sampled_from(Status),
        st.dates().map(lambda d: d.isoformat()),
        st.booleans(),
    ),
    min_size=1,
    max_size=6,
)


def build_vault(nodes: dict[str, tuple[Status, str, bool]]) -> Vault:
    vault = Vault(Path(tempfile.mkdtemp()))
    for name, (status, date, with_blueprint) in nodes.items():
        blueprint = f"research/math/{name.lower().replace(' ', '-')}/" if with_blueprint else ""
        (vault.path / f"{name}.md").write_text(
            zettel_text(
                status, date=date, summary=f"summary of {name}", blueprint=blueprint, title=name
            )
        )
    return vault


@given(nodes_strategy)
def test_every_node_lands_once_under_its_heading(
    nodes: dict[str, tuple[Status, str, bool]],
) -> None:
    vault = build_vault(nodes)
    text = ResultsIndex(vault.path / "Index.md").render(vault.nodes())
    for name, (status, _, with_blueprint) in nodes.items():
        entries = [line for line in text.splitlines() if line.startswith(f"- [[{name}]]")]
        assert len(entries) == 1
        assert f"summary of {name}." in entries[0]
        assert ("`research/math/" in entries[0]) == with_blueprint
        section = text.split(HEADINGS[status], 1)[1].split("\n##", 1)[0]
        assert f"- [[{name}]]" in section


@given(nodes_strategy)
def test_sections_sort_by_date_descending_then_name(
    nodes: dict[str, tuple[Status, str, bool]],
) -> None:
    vault = build_vault(nodes)
    text = ResultsIndex(vault.path / "Index.md").render(vault.nodes())
    by_name = {name: (status, date) for name, (status, date, _) in nodes.items()}
    listed = [
        line.split("]]")[0].removeprefix("- [[")
        for line in text.splitlines()
        if line.startswith("- [[")
    ]
    for heading in dict.fromkeys(HEADINGS.values()):
        group = [n for n in listed if HEADINGS[by_name[n][0]] == heading]
        assert group == sorted(sorted(group), key=lambda n: by_name[n][1], reverse=True)


def test_preamble_and_footer_survive_regeneration(root: Path) -> None:
    vault = Vault(root / "vault" / "Zettelkasten")
    index = ResultsIndex(vault.path / "Mathematics Results Index.md")
    text = index.render(vault.nodes())
    assert text.startswith("---\ndate: 2026-06-10\n---")
    assert "Preamble prose." in text
    assert text.endswith("Footer prose.\n\nLinks: [[Research]].\n")
    assert "- [[Dep]], a settled dep." in text
    assert "## In progress / open" in text


def test_rendering_is_idempotent(root: Path) -> None:
    vault = Vault(root / "vault" / "Zettelkasten")
    index = ResultsIndex(vault.path / "Mathematics Results Index.md")
    first = index.render(vault.nodes())
    index.path.write_text(first)
    assert index.render(vault.nodes()) == first


def test_a_missing_index_gets_a_minimal_preamble(tmp_path: Path) -> None:
    note = tmp_path / "Note.md"
    note.write_text(zettel_text(Status.SKETCHED, summary="s", title="Note"))
    text = ResultsIndex(tmp_path / "Fresh Index.md").render([Zettel(note)])
    assert text.startswith("# Fresh Index\n")
    assert "- [[Note]], s." in text

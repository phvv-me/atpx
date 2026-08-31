import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import Category, Frontmatter
from atpx.graph.frontmatter import split_slugs

from ..support import node_text, written

_NULL_SPELLINGS = ("null", "NULL", "~", "none", "None", "NoNe")

slugs = st.from_regex(r"[a-z][a-z0-9-]{0,12}", fullmatch=True).filter(
    lambda slug: slug.lower() not in {"null", "none"}
)
slug_lists = st.lists(slugs, min_size=1, max_size=4, unique=True)


@given(slug_lists)
def test_listed_reads_bracketed_and_bare_lists_alike(items: list[str]) -> None:
    joined = ", ".join(items)
    assert Frontmatter.listed(f"[{joined}]") == items
    assert Frontmatter.listed(joined) == items
    assert Frontmatter.listed("") == []


@given(depends=slug_lists, seeds=st.lists(st.integers(0, 10**10), min_size=1, max_size=4))
def test_parse_reads_the_contract_fields(depends: list[str], seeds: list[int]) -> None:
    node = written(
        node_text(
            front={
                "kind": "conjecture",
                "depends": f"[{', '.join(depends)}]",
                "serves": "[papers/iclr-2027]",
                "seeds": f"[{', '.join(map(str, seeds))}]",
                "judgments": "[judgments/draft.md]",
            }
        )
    )
    front = node.front
    assert front.status == "open" and front.kind == "conjecture"
    assert front.depends == depends and front.seeds == seeds
    assert front.serves == ["papers/iclr-2027"]
    assert front.judgments == ["judgments/draft.md"]
    assert front.problems == [] and front.present


def test_a_seed_that_is_not_an_integer_is_a_problem_not_a_crash() -> None:
    front = written(node_text(front={"seeds": "[7, soup]"})).front
    assert front.seeds == [7]
    assert front.problems == ["seeds entry 'soup' is not an integer"]


def test_a_seed_that_reads_null_is_absent_without_a_problem() -> None:
    front = written(node_text(front={"seeds": "[7, null]"})).front
    assert front.seeds == [7]
    assert front.problems == []


def test_a_missing_block_is_a_problem_not_a_crash() -> None:
    front = Frontmatter.parse("# Just Prose\n\nNo fences here.\n")
    assert not front.present
    assert front.problems == ["no frontmatter block"]
    assert front.status is None and front.depends == []


def test_category_derives_from_the_kind() -> None:
    assert Frontmatter(kind="probe-pool").category is Category.PROBE_POOL
    assert Frontmatter(kind="convention").category is Category.CONVENTION
    assert Frontmatter(kind="theorem").category is Category.CLAIM
    assert Frontmatter().category is Category.CLAIM


@given(items=slug_lists, spelling=st.sampled_from(_NULL_SPELLINGS))
def test_split_slugs_drops_a_null_spelling_and_names_it(items: list[str], spelling: str) -> None:
    found, implausible = split_slugs(f"[{', '.join([*items, spelling])}]")
    assert found == items
    assert implausible == [spelling]


@pytest.mark.parametrize("bad", ["not a slug", "not:real", "root/not real:slug"])
def test_split_slugs_drops_a_value_with_a_space_or_a_colon(bad: str) -> None:
    found, implausible = split_slugs(f"[real, {bad}]")
    assert found == ["real"]
    assert implausible == [bad]


def test_split_slugs_reads_an_empty_value_as_silently_absent() -> None:
    assert split_slugs("") == ([], [])


@pytest.mark.parametrize("spelling", _NULL_SPELLINGS)
def test_a_null_spelling_in_depends_is_dropped_but_reported(spelling: str) -> None:
    front = written(node_text(front={"depends": f"[dep, {spelling}]"})).front
    assert front.depends == ["dep"]
    assert front.problems == [f"depends entry {spelling!r} is not a plausible slug"]


def test_a_value_with_a_space_in_serves_is_dropped_but_reported() -> None:
    front = written(node_text(front={"serves": "[papers/iclr-2027, not a paper]"})).front
    assert front.serves == ["papers/iclr-2027"]
    assert front.problems == ["serves entry 'not a paper' is not a plausible slug"]


def test_superseded_by_reads_a_null_spelling_as_no_pointer() -> None:
    front = written(node_text(front={"superseded_by": "null"})).front
    assert front.superseded_by == ""
    assert front.problems == ["superseded_by entry 'null' is not a plausible slug"]


def test_a_relation_only_key_reports_a_null_spelling_though_it_stores_no_field() -> None:
    """`successor_of` never becomes a `Frontmatter` field, but a bad value still surfaces."""
    front = written(node_text(front={"successor_of": "null"})).front
    assert front.problems == ["successor_of entry 'null' is not a plausible slug"]


def test_a_relation_only_key_reports_an_implausible_value() -> None:
    front = written(node_text(front={"shadows": "width-law, not real"})).front
    assert front.problems == ["shadows entry 'not real' is not a plausible slug"]

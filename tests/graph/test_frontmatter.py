from hypothesis import given
from hypothesis import strategies as st

from atpx import Category, Frontmatter

from ..support import node_text, written

slugs = st.from_regex(r"[a-z][a-z0-9-]{0,12}", fullmatch=True)
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

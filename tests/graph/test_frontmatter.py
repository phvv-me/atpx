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
                "type": "conjecture",
                "depends": f"[{', '.join(depends)}]",
                "serves": "[papers/iclr-2027]",
                "seeds": f"[{', '.join(map(str, seeds))}]",
                "judgments": "[judgments/draft.md]",
            }
        )
    )
    front = node.front
    assert front.status == "open" and front.type == "conjecture"
    assert front.depends == depends and front.seeds == seeds
    assert front.serves == ["papers/iclr-2027"]
    assert front.judgments == ["judgments/draft.md"]
    assert front.problems == [] and front.present


def test_the_okf_catalog_keys_are_read_whole_and_flagged_by_nothing() -> None:
    front = written(
        node_text(
            front={
                "type": "experiment",
                "title": "The Fused Block Law",
                "description": "Blocks accumulate exactly.",
                "resource": "probes/law.py",
                "tags": "[determinism, gemm]",
                "timestamp": "2026-09-10T12:00:00Z",
                "generated": "{by: mainboard, at: 2026-09-10}",
                "verified": "{by: pedro}",
                "sources": "[arxiv:2509.00001]",
                "stale_after": "2027-01-01",
                "okf_version": "0.2",
            }
        )
    ).front
    assert front.type == "experiment" and front.title == "The Fused Block Law"
    assert front.description == "Blocks accumulate exactly." and front.resource == "probes/law.py"
    assert front.tags == ["determinism", "gemm"] and front.sources == ["arxiv:2509.00001"]
    assert front.generated == "{by: mainboard, at: 2026-09-10}"
    assert front.verified == "{by: pedro}" and front.stale_after == "2027-01-01"
    assert front.okf_version == "0.2" and front.problems == []


def test_the_ledger_status_vocabulary_is_never_validated_against_the_format() -> None:
    """OKF spells a status draft/stable/deprecated; the ladder here is the one that governs."""
    front = written(node_text("registered")).front
    assert front.status == "registered" and front.problems == []


def test_a_timestamp_that_is_not_iso_8601_is_a_problem_not_a_crash() -> None:
    front = written(node_text(front={"timestamp": "last tuesday"})).front
    assert front.timestamp == "last tuesday"
    assert front.problems == ["timestamp 'last tuesday' is not ISO 8601"]


def test_aliases_read_as_slugs_and_an_unslug_like_one_is_named() -> None:
    front = written(node_text(front={"aliases": "[old-name, older_name]"})).front
    assert front.aliases == ["old-name", "older_name"] and front.problems == []
    broken = written(node_text(front={"aliases": "[not a slug]"})).front
    assert broken.aliases == []
    assert broken.problems == ["aliases entry 'not a slug' is not a plausible slug"]


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


def test_category_derives_from_the_type() -> None:
    assert Frontmatter(type="probe-pool").category is Category.PROBE_POOL
    assert Frontmatter(type="convention").category is Category.CONVENTION
    assert Frontmatter(type="theorem").category is Category.CLAIM
    assert Frontmatter().category is Category.CLAIM


def test_the_legacy_kind_key_is_read_as_the_okf_type() -> None:
    assert written(node_text(front={"kind": "probe-pool"})).front.type == "probe-pool"
    assert written(node_text(front={"kind": "lemma", "type": "theorem"})).front.type == "theorem"


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

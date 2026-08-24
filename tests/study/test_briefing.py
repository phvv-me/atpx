from pathlib import Path

from atpx import Blueprint, EvidenceStore, Node, Workspace
from atpx.briefing import Briefing, JudgmentLedger, last_judgment

from ..support import FakeRunner, stamped


def test_judgment_ledger_roundtrips_and_starts_empty(root: Path) -> None:
    ledger = JudgmentLedger(root / "research" / "math" / "demo")
    assert ledger.latest("demo") is None
    node = Node(root / "research" / "math" / "demo" / "node.md")
    path = ledger.record(node)
    assert path == ledger.path("demo")
    judgment = ledger.latest("demo")
    assert judgment is not None
    assert judgment.text == node.text and judgment.timestamp.endswith("Z")


def test_brief_bundles_node_deps_evidence_judgment_and_files(space: Workspace) -> None:
    store = EvidenceStore(space.blueprints / "demo")
    store.append(stamped(claim="demo/ok"))
    space.log("demo", "refuter", "ties", "no counterexample found.")
    text = space.brief("demo")
    assert text.startswith("# Brief for demo") and "Status open" in text
    assert "A claim using [[dep]]." in text and "- [[dep]] is sketched" in text
    assert f"- {store.hostname} holds 1 certificates, latest at git_rev 0000000 (stale)" in text
    assert "- [refuter/ties 2" in text and "no counterexample found." in text
    assert "- atpx.toml" in text and "- node.md" in text


def test_brief_marks_current_evidence_and_missing_judgment(space: Workspace) -> None:
    current = stamped(claim="demo/ok").model_copy(update={"git_rev": "unknown"})
    EvidenceStore(space.blueprints / "demo").append(current)
    text = space.brief("demo")
    assert "(current)" in text
    assert "No judgment logged yet." in text


def test_brief_of_a_bare_node_says_so(*, root: Path, tmp_path: Path) -> None:
    space = Workspace(root, runner=FakeRunner())
    blueprint = Blueprint(slug="dep", directory=tmp_path, claims={})
    node = space.nodes.find("dep")
    text = Briefing(blueprint, node, space.nodes, "unknown").render()
    assert "No blueprint dependencies." in text
    assert "No evidence recorded yet." in text
    assert "No judgment logged yet." in text


def test_last_judgment_is_the_latest_refuter_line(root: Path) -> None:
    node = Node(root / "research" / "math" / "demo" / "node.md")
    assert last_judgment(node) is None
    node.append_log("- [refuter/ties 2026-06-11] first ruling.")
    node.append_log("- [refuter/tilt 2026-06-12] second ruling.")
    node.append_log("- [prover/more 2026-06-12] not a ruling.")
    entry = last_judgment(node)
    assert entry is not None
    assert str(entry) == "- [refuter/tilt 2026-06-12] second ruling."


def test_judge_brief_before_any_judgment(space: Workspace) -> None:
    text = space.judge_brief("demo")
    assert text.startswith("# Judge brief for demo")
    assert "No judgment recorded yet" in text


def test_judge_brief_diffs_the_node_and_lists_newer_claims(space: Workspace) -> None:
    ruling = space.blueprints / "demo" / "ruling.md"
    ruling.write_text("NONE.\n")
    space.settle("demo", "sketched", "ruling.", judgment=str(ruling))
    space.log("demo", "prover", "lemma", "a new lemma landed.")
    newer = stamped(claim="demo/ok").model_copy(update={"timestamp": "2099-01-01T00:00:00+00:00"})
    EvidenceStore(space.blueprints / "demo").append(newer)
    text = space.judge_brief("demo")
    assert "Last judged 2" in text
    assert "+- [prover/lemma" in text
    assert "- ok gained 1 certificates" in text


def test_judge_brief_counts_unprefixed_claims_under_their_full_id(space: Workspace) -> None:
    ruling = space.blueprints / "demo" / "ruling.md"
    ruling.write_text("NONE.\n")
    space.settle("demo", "sketched", "ruling.", judgment=str(ruling))
    fit = stamped(claim="fit data.csv").model_copy(
        update={"timestamp": "2099-01-01T00:00:00+00:00"}
    )
    EvidenceStore(space.blueprints / "demo").append(fit)
    text = space.judge_brief("demo")
    assert "- fit data.csv gained 1 certificates" in text


def test_judge_brief_with_nothing_new_says_so(space: Workspace) -> None:
    old = stamped(claim="demo/ok")
    EvidenceStore(space.blueprints / "demo").append(old)
    ruling = space.blueprints / "demo" / "ruling.md"
    ruling.write_text("NONE.\n")
    space.settle("demo", "sketched", "ruling.", judgment=str(ruling))
    text = space.judge_brief("demo")
    assert "Unchanged." in text
    assert "None." in text

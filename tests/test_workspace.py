import json
import os
import stat
from pathlib import Path

import pytest
from plumbum import local

from atpx.blueprint import REQUIREMENTS, Blueprint
from atpx.engines import (
    ArxivEngine,
    LoogleEngine,
    MpmathEngine,
    OeisEngine,
    SearchError,
    VaultEngine,
    ZbmathEngine,
)
from atpx.evidence import EvidenceStore
from atpx.roles import Status
from atpx.workspace import ChefeRunner, CrossCheckError, Workspace, find_root, workspace

from .conftest import FakeRunner, evidence_entries, stamped

UNSAT = "(set-logic QF_LIA)(declare-const x Int)(assert (> x 0))(assert (< x 0))"
SAT = "(set-logic QF_LIA)(declare-const x Int)(assert (> x 0))"


def test_find_root_walks_past_blueprint_manifests(root: Path) -> None:
    assert find_root(root / "research" / "math" / "demo") == root
    assert workspace(root).root == root


def test_find_root_fails_loudly_outside_a_workspace(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="atpx.toml"):
        find_root(tmp_path)


def test_workspace_discovers_root_from_the_cwd(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(root / "vault")
    assert workspace().root == root


def test_check_stamps_and_persists_evidence(ws: tuple[Workspace, FakeRunner]) -> None:
    space, runner = ws
    certificate = space.check("demo", "ok", seed=7)
    assert runner.calls == [["python", "research/math/demo/checks.py", "ok"]]
    assert certificate.ok and certificate.claim == "demo/ok" and certificate.seed == 7
    assert certificate.result == {"passed": True}
    entries = evidence_entries(space.blueprints / "demo")
    assert [entry["claim"] for entry in entries] == ["demo/ok"]
    space.check("demo", "ok")
    assert len(evidence_entries(space.blueprints / "demo")) == 2


def test_check_records_failures_too(root: Path) -> None:
    space = Workspace(root, runner=FakeRunner(exit_status=3, output="boom\n"))
    certificate = space.check("demo", "ok")
    assert not certificate.ok and certificate.exit_status == 3
    assert certificate.result == {"output": "boom"}


def test_check_skips_claims_this_host_cannot_run(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: False)
    certificate = space.check("demo", "gpu")
    assert certificate.ok and certificate.result == {"skipped": True, "requires": "cuda"}
    assert runner.calls == []
    assert not (space.blueprints / "demo" / "evidence").exists()


def test_check_runs_required_claims_when_the_host_qualifies(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: True)
    certificate = space.check("demo", "gpu")
    assert certificate.result == {"passed": True}
    assert runner.calls == [["python", "research/math/demo/checks.py", "gpu"]]
    assert len(evidence_entries(space.blueprints / "demo")) == 1


def test_payload_takes_the_last_json_line(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    assert space.payload('noise\n{"a": 1}\n{"b": [2]}\ntrailer') == {"b": [2]}
    assert space.payload('{"broken": \nplain tail') == {"output": '{"broken": \nplain tail'}


def test_status_groups_by_ladder(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    assert space.status() == {
        "open": ["Demo Node"],
        "in_progress": ["Blocked"],
        "sketched": ["Dep"],
    }


def test_graph_lists_the_frontier(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    assert [node["node"] for node in space.graph()] == ["Demo Node"]


def test_log_appends_a_role_stamped_line(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    line = space.log("Demo Node", "refuter", "numeric", "no counterexample.")
    assert line.startswith("- [refuter/numeric 2") and line.endswith("no counterexample.")
    assert line in space.vault.find("Demo Node").text
    assert space.vault.find("Demo Node").status is Status.OPEN


def test_log_gates_transitions_by_role(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    before = space.vault.find("Demo Node").text
    with pytest.raises(PermissionError, match="prover may not set sketched"):
        space.log("Demo Node", "prover", "judge", "looks done.", status="sketched")
    assert space.vault.find("Demo Node").text == before
    space.log("Demo Node", "refuter", "adversarial", "NONE.", status="sketched")
    assert space.vault.find("Demo Node").status is Status.SKETCHED


def test_only_the_formalizer_verifies(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    with pytest.raises(PermissionError, match="refuter may not set verified"):
        space.log("Demo Node", "refuter", "lean", "built.", status="verified")
    space.log("Demo Node", "formalizer", "lean", "build green.", status="verified")
    assert space.vault.find("Demo Node").status is Status.VERIFIED


def test_index_regenerates_and_writes(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    text = space.index()
    assert "- [[Demo Node]], a demo claim holds. `research/math/demo/`" in text
    assert space.results_index.path.read_text() != text
    assert space.index(write=True) == text
    assert space.results_index.path.read_text() == text


def test_compute_certifies_an_engine_result(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    certificate = space.compute("sympy", "evaluate", "2**10")
    assert certificate.engine == "sympy" and certificate.ok
    assert str(certificate.result).startswith("1024.0")


def test_prove_closes_smt_goals_and_names_the_engine(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    certificate = space.prove(UNSAT)
    assert certificate.engine == "z3" and certificate.ok
    assert certificate.result == {"closed": True, "attempts": {"z3": "unsat"}}


def test_prove_records_every_failed_attempt(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    certificate = space.prove(SAT)
    assert certificate.engine == "atpx" and not certificate.ok
    assert certificate.result == {"closed": False, "attempts": {"z3": "sat", "cvc5": "sat"}}


def test_prove_tptp_without_provers_leaves_the_goal_open(
    ws: tuple[Workspace, FakeRunner], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    space, _ = ws
    monkeypatch.setenv("PATH", str(tmp_path))
    certificate = space.prove("fof(g, conjecture, a => a).")
    assert certificate.result == {"closed": False, "attempts": {}} and not certificate.ok


def test_prove_rejects_undetectable_syntax(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    with pytest.raises(ValueError, match="cannot detect goal syntax"):
        space.prove("just words")


def test_cross_check_certifies_agreement(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    certificate = space.cross_check("evaluate", "sqrt(2)")
    assert certificate.ok
    assert isinstance(certificate.result, dict)
    assert certificate.result["agree"] is True
    results = certificate.result["results"]
    assert isinstance(results, dict)
    assert set(results) == {"sympy", "mpmath"}


def test_cross_check_flags_disagreement(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, _ = ws
    monkeypatch.setattr(MpmathEngine, "execute", lambda self, payload: "3.0")
    certificate = space.cross_check("evaluate", "sqrt(2)", engines=["sympy", "mpmath"])
    assert not certificate.ok
    assert isinstance(certificate.result, dict)
    assert certificate.result["agree"] is False


def test_cross_check_needs_two_independent_engines(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    with pytest.raises(CrossCheckError, match="at least two"):
        space.cross_check("factor", "720")


def reply(engine_name: str) -> str:
    """A one-hit JSON reply a fake search engine returns."""
    return json.dumps([{"id": f"{engine_name}-1", "title": f"hit from {engine_name}"}])


def test_recall_certifies_hits_per_source(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, _ = ws
    roots: list[Path] = []

    def vault_reply(engine: VaultEngine, payload: str) -> str:
        roots.append(engine.cwd)
        return reply("vault")

    monkeypatch.setattr(VaultEngine, "available", lambda self: True)
    monkeypatch.setattr(VaultEngine, "execute", vault_reply)
    monkeypatch.setattr(OeisEngine, "execute", lambda self, payload: reply("oeis"))
    certificate = space.recall("kolakoski", sources=["vault", "oeis"])
    assert certificate.ok and certificate.engine == "atpx"
    assert certificate.claim == "recall kolakoski"
    assert certificate.result == {
        "hits": {
            "vault": [{"id": "vault-1", "title": "hit from vault"}],
            "oeis": [{"id": "oeis-1", "title": "hit from oeis"}],
        },
        "errors": {},
    }
    assert roots == [space.root]


def test_recall_defaults_to_every_search_source(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, _ = ws
    monkeypatch.setattr(VaultEngine, "available", lambda self: True)
    for engine in (VaultEngine, OeisEngine, LoogleEngine, ArxivEngine, ZbmathEngine):
        monkeypatch.setattr(engine, "execute", lambda self, payload: "[]")
    certificate = space.recall("anything")
    assert isinstance(certificate.result, dict)
    hits = certificate.result["hits"]
    assert isinstance(hits, dict)
    assert list(hits) == ["vault", "oeis", "loogle", "arxiv", "zbmath"]


def test_recall_records_failures_and_exits_nonzero(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, _ = ws

    def down(engine: OeisEngine, payload: str) -> str:
        raise SearchError("oeis: connection refused")

    monkeypatch.setattr(OeisEngine, "execute", down)
    monkeypatch.setattr(LoogleEngine, "execute", lambda self, payload: reply("loogle"))
    certificate = space.recall("anything", sources=["oeis", "loogle"])
    assert not certificate.ok
    assert certificate.result == {
        "hits": {"loogle": [{"id": "loogle-1", "title": "hit from loogle"}]},
        "errors": {"oeis": "oeis: connection refused"},
    }


def test_recall_reports_unavailable_sources(
    ws: tuple[Workspace, FakeRunner], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    space, _ = ws
    monkeypatch.setenv("PATH", str(tmp_path))
    certificate = space.recall("anything", sources=["vault"])
    assert not certificate.ok
    assert certificate.result == {
        "hits": {},
        "errors": {"vault": "vault is not available on this host"},
    }


def test_chefe_runner_invokes_chefe_from_the_root(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "chefe"
    fake.write_text('#!/bin/sh\necho "$@"\npwd\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    local.env.path.insert(0, str(tmp_path))
    try:
        code, output = ChefeRunner(root)(["python", "checks.py"])
    finally:
        local.env.path.remove(str(tmp_path))
    assert code == 0
    assert output.splitlines() == ["run python checks.py", str(root)]


def test_verify_reruns_runnable_claims_and_flags_stale_evidence(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, runner = ws
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: False)
    prior = stamped(claim="demo/ok").model_copy(update={"git_rev": "feedbee"})
    EvidenceStore(space.blueprints / "demo").append(prior)
    certificate = space.verify()
    assert certificate.ok and certificate.claim == "verify"
    assert certificate.result == {
        "demo": {
            "ok": {"state": "fresh", "stale": True},
            "gpu": {"state": "skipped", "stale": False},
        }
    }
    assert runner.calls == [["python", "research/math/demo/checks.py", "ok"]]
    assert len(evidence_entries(space.blueprints / "demo")) == 2


def test_verify_one_slug_reports_failures(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    space = Workspace(root, runner=FakeRunner(exit_status=2, output="boom\n"))
    monkeypatch.setitem(REQUIREMENTS, "cuda", lambda: True)
    certificate = space.verify("demo")
    assert not certificate.ok and certificate.claim == "verify demo"
    assert certificate.result == {
        "demo": {
            "ok": {"state": "failed", "stale": False},
            "gpu": {"state": "failed", "stale": False},
        }
    }


def test_stale_claims_judge_only_the_latest_certificate(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, _ = ws
    store = EvidenceStore(space.blueprints / "demo")
    newest = stamped(claim="demo/ok").model_copy(
        update={"git_rev": "current", "timestamp": "2026-06-12T02:00:00+00:00"}
    )
    older = stamped(claim="demo/ok").model_copy(
        update={"git_rev": "feedbee", "timestamp": "2026-06-12T01:00:00+00:00"}
    )
    store.append(newest)
    store.append(older)
    blueprint = Blueprint.load(space.blueprints / "demo")
    assert space.stale_claims(blueprint, "current") == frozenset()
    assert space.stale_claims(blueprint, "elsewhere") == frozenset({"ok"})


def test_connect_fingerprints_evidence_against_oeis(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, _ = ws
    theta = stamped(claim="demo/ok").model_copy(
        update={"result": {"theta": [1, 196560, 16773120, 398034000], "noise": [1, 2]}}
    )
    EvidenceStore(space.blueprints / "demo").append(theta)
    monkeypatch.setattr(OeisEngine, "execute", lambda self, payload: reply("oeis"))
    certificate = space.connect("demo")
    assert certificate.ok and certificate.claim == "connect demo"
    assert certificate.result == {
        "1, 196560, 16773120, 398034000": {
            "hits": {"oeis": [{"id": "oeis-1", "title": "hit from oeis"}]},
            "errors": {},
        }
    }


def test_connect_surfaces_oeis_failures(
    ws: tuple[Workspace, FakeRunner], monkeypatch: pytest.MonkeyPatch
) -> None:
    space, _ = ws
    run = stamped(claim="demo/ok").model_copy(update={"result": [2, 3, 5, 7]})
    EvidenceStore(space.blueprints / "demo").append(run)

    def down(engine: OeisEngine, payload: str) -> str:
        raise SearchError("oeis: connection refused")

    monkeypatch.setattr(OeisEngine, "execute", down)
    certificate = space.connect("demo")
    assert not certificate.ok


def test_connect_without_sequences_is_clean(ws: tuple[Workspace, FakeRunner]) -> None:
    space, _ = ws
    certificate = space.connect("demo")
    assert certificate.ok and certificate.result == {}


def test_strategies_and_lean_candidates_render_tables(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, _ = ws
    strategies = space.strategies()
    assert strategies.splitlines()[0] == "| strategy | lines | nodes | closed | close rate |"
    assert "| start | 3 | 3 | 1 | 33% |" in strategies
    candidates = space.lean_candidates()
    assert candidates.splitlines()[0] == "| node | backlinks | length | score |"
    assert "| [[Dep]] | 2 |" in candidates


def test_refuter_logs_snapshot_the_node_into_the_judgment_ledger(
    ws: tuple[Workspace, FakeRunner],
) -> None:
    space, _ = ws
    judgments = space.blueprints / "demo" / "judgments"
    space.log("Demo Node", "prover", "lemma", "not a ruling.")
    assert not judgments.exists()
    space.log("Dep", "refuter", "ties", "no blueprint, no snapshot.")
    assert not judgments.exists()
    space.log("Demo Node", "refuter", "ties", "ruling.", status="sketched")
    snapshot = json.loads((judgments / "Demo Node.json").read_text())
    assert "ruling." in snapshot["text"] and "status: sketched" in snapshot["text"]

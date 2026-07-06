import json
import stat
from collections.abc import Callable, Coroutine, Iterator
from pathlib import Path
from typing import ClassVar

import pytest

from atpx.certificate import Certificate, short_hostname
from atpx.engines import Capability, Engine, SearchEngine
from atpx.roles import Status
from atpx.workspace import Workspace


def zettel_text(
    status: Status | str | None = Status.OPEN,
    date: str = "2026-06-10",
    summary: str = "",
    blueprint: str = "",
    title: str = "Demo Node",
    body: str = "A claim using [[Dep]].",
    log: str | None = "- [prover/start 2026-06-10] opened.",
) -> str:
    """Render a vault note in the house format from its parts."""
    front = [f"status: {Status(status).value}"] if status else []
    front += [f"date: {date}"]
    front += [f"summary: {summary}"] if summary else []
    front += [f"blueprint: {blueprint}"] if blueprint else []
    head = "\n".join(["---", *front, "---"])
    sections = [head, "#math #proof #ai-generated", f"# {title}", body]
    if log is not None:
        sections += [f"## Log    (append-only: [who/tag YYYY-MM-DD] one line)\n{log}"]
    return "\n\n".join(sections) + "\n"


def result_of(certificate: Certificate):
    """The certificate result as plain parsed JSON, convenient to index in asserts."""
    return json.loads(certificate.model_dump_json())["result"]


def stamped(claim: str = "demo/ok", exit_status: int = 0) -> Certificate:
    """A cheap certificate carrying this host's name, no subprocess provenance."""
    return Certificate(
        claim=claim,
        result={"ok": True},
        engine="atpx",
        engine_version="0",
        hostname=short_hostname(),
        device="test",
        git_rev="0000000",
        timestamp="2026-06-12T00:00:00+00:00",
        exit_status=exit_status,
    )


class FakeRunner:
    """Claim runner double recording argv and replying with a canned line."""

    def __init__(self, exit_status: int = 0, output: str = '{"passed": true}\n') -> None:
        self.exit_status = exit_status
        self.output = output
        self.calls: list[list[str]] = []

    async def __call__(self, argv: list[str]) -> tuple[int, str]:
        self.calls.append(argv)
        return self.exit_status, self.output


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A minimal workspace: root manifest, one blueprint, and a three-node vault."""
    (tmp_path / "atpx.toml").write_text("[workspace]\n")
    blueprint = tmp_path / "research" / "math" / "demo"
    blueprint.mkdir(parents=True)
    (blueprint / "atpx.toml").write_text(
        'zettel = "Demo Node"\n\n[claims]\nok = "python {dir}/checks.py ok"\n\n'
        '[claims.gpu]\ncommand = "python {dir}/checks.py gpu"\nrequires = "cuda"\n'
    )
    vault = tmp_path / "vault" / "Zettelkasten"
    vault.mkdir(parents=True)
    (vault / "Demo Node.md").write_text(
        zettel_text(summary="a demo claim holds", blueprint="research/math/demo/")
    )
    (vault / "Dep.md").write_text(
        zettel_text(Status.SKETCHED, title="Dep", body="Settled.", summary="a settled dep")
    )
    (vault / "Blocked.md").write_text(
        zettel_text(Status.IN_PROGRESS, title="Blocked", body="Needs [[Demo Node]].")
    )
    (vault / "Mathematics Results Index.md").write_text(
        "---\ndate: 2026-06-10\n---\n#structure #math\n\n# Mathematics Results Index\n\n"
        "Preamble prose.\n\n## Sketched (refuter-survived, usable)\n\n"
        "- [[Dep]], a settled dep.\n\nFooter prose.\n\nLinks: [[Research]].\n"
    )
    return tmp_path


@pytest.fixture
def ws(root: Path) -> tuple[Workspace, FakeRunner]:
    """A workspace over the fixture root with a recording fake runner."""
    runner = FakeRunner()
    return Workspace(root, runner=runner), runner


def evidence_entries(blueprint: Path) -> list[dict[str, object]]:
    """Parsed entries of every evidence file under a blueprint."""
    files = sorted((blueprint / "evidence").glob("*.json"))
    return [entry for f in files for entry in json.loads(f.read_text())]


def script(directory: Path, name: str, body: str) -> Path:
    """Write an executable POSIX shell script on disk and return its path."""
    path = directory / name
    path.write_text(f"#!/bin/sh\n{body}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.fixture
def fake_chefe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[str], Path]:
    """A factory that installs a `chefe` with a given body, alone on PATH."""
    monkeypatch.setenv("PATH", str(tmp_path))
    return lambda body: script(tmp_path, "chefe", body)


def reply(engine_name: str) -> str:
    """A one-hit JSON reply a fake search engine returns."""
    return json.dumps([{"id": f"{engine_name}-1", "title": f"hit from {engine_name}"}])


def fetcher(engine_name: str) -> Callable[[SearchEngine, str], Coroutine[None, None, str]]:
    """An async fetch double replying with one canned hit."""

    async def fetch(engine: SearchEngine, payload: str) -> str:
        return reply(engine_name)

    return fetch


@pytest.fixture
def ghost_engine() -> Iterator[type[Engine]]:
    """A registered engine whose module never exists, unenrolled again on teardown.

    The cleanup keeps the registry enumeration tests (`Engine.supporting`)
    order-independent: no other test ever sees the ghost.
    """

    class GhostEngine(Engine):
        name = "ghost"
        module: ClassVar[str] = "nosuch_module_anywhere"
        distribution: ClassVar[str] = "nosuch-dist"
        capability: ClassVar[Capability] = Capability.SEARCH

        def execute(self, payload: str) -> str:
            return payload

    yield GhostEngine
    Engine.registry_entries.remove(GhostEngine)

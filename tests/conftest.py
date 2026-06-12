import json
from pathlib import Path

import pytest

from atpx.certificate import Certificate, short_hostname
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

    def __call__(self, argv: list[str]) -> tuple[int, str]:
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

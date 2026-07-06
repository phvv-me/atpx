import asyncio
import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from atpx.blueprint import Blueprint
from atpx.evidence import EvidenceStore
from atpx.running import ChefeRunner, Running, payload, stale_claims
from atpx.workspace import Workspace

from .conftest import FakeRunner, stamped


def test_payload_takes_the_last_json_line() -> None:
    output = 'noise\n{"broken": \n{"margin": 0.25}\ntrailing prose'
    assert payload(output) == {"margin": 0.25}
    assert payload("no json at all") == {"output": "no json at all"}


def test_payload_falls_back_when_the_only_json_line_is_broken() -> None:
    assert payload('{"broken":') == {"output": '{"broken":'}


def test_payload_reads_indented_json() -> None:
    assert payload('prose\n   {"a": 1}') == {"a": 1}


def test_payload_takes_the_last_value_of_an_interleaved_line() -> None:
    assert payload('{"a": 1}{"b": 2}') == {"b": 2}
    assert payload('{"a": 1} {"b": 2}') == {"b": 2}
    assert payload('[1, 2] {"b": 2}\tnot json trailer') == {"b": 2}


@given(st.dictionaries(st.text(), st.integers(), max_size=3), st.text())
def test_payload_recovers_the_last_printed_object(result: dict[str, int], noise: str) -> None:
    assert payload(noise + "\n" + json.dumps(result) + "\n") == result


class SleepyRunner:
    """A runner that outlives any reasonable timeout."""

    async def __call__(self, argv: list[str]) -> tuple[int, str]:
        await asyncio.sleep(60)
        return 0, "never"


def test_bounded_stamps_exit_124_on_expiry(tmp_path: Path) -> None:
    running = Running(SleepyRunner(), tmp_path)
    exit_status, output = asyncio.run(running.bounded(["sleep"], 0.01))
    assert exit_status == 124 and "timed out" in output


def test_chefe_runner_invokes_chefe_from_the_root(root: Path, fake_chefe) -> None:
    fake_chefe('echo "chefe ran: $@"')
    exit_status, output = asyncio.run(ChefeRunner(root)(["python", "checks.py"]))
    assert exit_status == 0 and "chefe ran: run python checks.py" in output


def test_swept_returns_one_certificate_per_claim(root: Path) -> None:
    running = Running(FakeRunner(), root)
    blueprint = Blueprint.load(root / "research" / "math" / "demo")
    fresh = asyncio.run(running.swept(blueprint, ["ok", "gpu"]))
    assert set(fresh) == {"ok", "gpu"}
    assert all(certificate.ok for certificate in fresh.values())


def test_stale_claims_judge_only_the_latest_certificate(root: Path) -> None:
    store = EvidenceStore(root / "research" / "math" / "demo")
    old = stamped("demo/ok").model_copy(update={"timestamp": "2026-06-01T00:00:00+00:00"})
    store.append(old)
    space = Workspace(root, runner=FakeRunner())
    blueprint = space.register("demo", "ok")
    assert stale_claims(blueprint, "0000000") == frozenset()
    assert stale_claims(blueprint, "1111111") == frozenset({"ok"})


def test_stale_claims_keep_the_newest_of_two_certificates(root: Path) -> None:
    store = EvidenceStore(root / "research" / "math" / "demo")
    newer = stamped("demo/ok").model_copy(update={"timestamp": "2026-06-12T00:00:00+00:00"})
    older = stamped("demo/ok").model_copy(
        update={"timestamp": "2026-06-01T00:00:00+00:00", "git_rev": "9999999"}
    )
    store.append(newer)
    store.append(older)
    space = Workspace(root, runner=FakeRunner())
    blueprint = space.register("demo", "ok")
    assert stale_claims(blueprint, "0000000") == frozenset()


def test_stale_claims_trust_any_host_at_the_current_revision(root: Path) -> None:
    """A later run on another host at another revision must not shadow fresh local evidence."""
    directory = root / "research" / "math" / "demo"
    EvidenceStore(directory).append(stamped("demo/ok"))
    foreign = stamped("demo/ok").model_copy(
        update={
            "hostname": "elsewhere",
            "timestamp": "2099-01-01T00:00:00+00:00",
            "git_rev": "9999999",
        }
    )
    EvidenceStore(directory, hostname="elsewhere").append(foreign)
    blueprint = Blueprint.load(directory)
    assert stale_claims(blueprint, "0000000") == frozenset()
    assert stale_claims(blueprint, "1111111") == frozenset({"ok"})


def test_stale_claims_skip_certificates_outside_the_slug_convention(root: Path) -> None:
    EvidenceStore(root / "research" / "math" / "demo").append(stamped("fit data.csv"))
    blueprint = Blueprint.load(root / "research" / "math" / "demo")
    assert stale_claims(blueprint, "1111111") == frozenset()

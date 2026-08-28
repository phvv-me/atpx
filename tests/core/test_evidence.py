import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from threading import Barrier, Thread

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import Certificate, EvidenceStore
from atpx.core import EvidenceError, TornLedger

from ..support import stamped

claims = st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=5)
_WORKERS = 8


def torn(path: Path, *lines: str) -> None:
    """Overwrite one stream ledger with the given raw lines, whatever they hold."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{line}\n" for line in lines))


@given(claims)
def test_appends_accumulate_in_order(claims: Sequence[str]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = EvidenceStore(Path(directory))
        for claim in claims:
            store.append(stamped(claim=claim))
        assert [entry.claim for entry in store.read()] == list(claims)


@given(claims)
def test_every_append_adds_exactly_one_line_and_rewrites_nothing(claims: Sequence[str]) -> None:
    """The append-only property: the stream only ever grows, one line per certificate."""
    with tempfile.TemporaryDirectory() as directory:
        store = EvidenceStore(Path(directory))
        prefixes = []
        for claim in claims:
            store.append(stamped(claim=claim))
            prefixes.append(store.path.read_text())
        lines = store.path.read_text().split("\n")[:-1]
        assert len(lines) == len(claims)
        pairs = zip(prefixes, prefixes[1:], strict=False)
        assert all(later.startswith(earlier) for earlier, later in pairs)


def test_concurrent_appends_never_lose_a_certificate(tmp_path: Path) -> None:
    """A file lock serializes racing writers, so no concurrent append drops a certificate."""
    start = Barrier(_WORKERS)

    def append_one(index: int) -> None:
        start.wait()
        EvidenceStore(tmp_path).append(stamped(claim=f"claim-{index}"))

    threads = [Thread(target=append_one, args=(index,)) for index in range(_WORKERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    landed = {entry.claim for entry in EvidenceStore(tmp_path).read()}
    assert landed == {f"claim-{index}" for index in range(_WORKERS)}


def test_read_before_any_write_is_empty(tmp_path: Path) -> None:
    assert EvidenceStore(tmp_path).read() == []


def test_each_host_writes_only_its_own_stream(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    path = store.append(stamped())
    assert path == tmp_path / "evidence" / f"{store.hostname}.ndjson"


def test_a_foreign_certificate_is_refused(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path, hostname="elsewhere")
    with pytest.raises(EvidenceError, match="cannot enter"):
        store.append(stamped())


def test_a_ledger_holding_foreign_evidence_is_refused(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    foreign = stamped().model_copy(update={"hostname": "elsewhere"})
    torn(store.path, foreign.model_dump_json())
    with pytest.raises(EvidenceError, match="foreign evidence"):
        store.append(stamped())


def test_ledgers_read_every_host_file(tmp_path: Path) -> None:
    assert EvidenceStore.ledgers(tmp_path) == {}
    mine = EvidenceStore(tmp_path)
    mine.append(stamped(claim="a"))
    foreign = stamped(claim="b").model_copy(update={"hostname": "elsewhere"})
    EvidenceStore(tmp_path, hostname="elsewhere").append(foreign)
    ledgers = EvidenceStore.ledgers(tmp_path)
    assert set(ledgers) == {mine.hostname, "elsewhere"}
    assert [entry.claim for entry in ledgers[mine.hostname]] == ["a"]
    assert [entry.claim for entry in ledgers["elsewhere"]] == ["b"]


@given(
    before=st.integers(min_value=0, max_value=4),
    after=st.integers(min_value=1, max_value=4),
)
def test_one_torn_line_costs_only_itself(*, before: int, after: int) -> None:
    """The whole point of the stream: a truncated record hides no certificate but its own."""
    with tempfile.TemporaryDirectory() as directory:
        store = EvidenceStore(Path(directory))
        surviving = [f"head-{index}" for index in range(before)]
        surviving += [f"tail-{index}" for index in range(after)]
        lines = [stamped(claim=claim).model_dump_json() for claim in surviving]
        lines.insert(before, '{"claim": "torn", "result": {"output": "cut mid')
        torn(store.path, *lines)
        with pytest.warns(TornLedger, match="does not decode as JSON"):
            assert [entry.claim for entry in store.read()] == surviving


def test_a_torn_line_names_where_it_sits(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    torn(store.path, stamped().model_dump_json(), "{not json", "", '["not", "a", "certificate"]')
    with pytest.warns(TornLedger) as warned:
        assert len(store.read()) == 1
    reported = " ".join(str(record.message) for record in warned)
    assert f"{store.path}:2" in reported and f"{store.path}:4" in reported


def test_blank_lines_are_not_torn_records(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    torn(store.path, "", stamped().model_dump_json(), "   ", "")
    assert [entry.claim for entry in store.read()] == ["demo/ok"]


def test_the_pre_migration_array_reads_transparently_beside_the_stream(tmp_path: Path) -> None:
    """The migration: read both, write the stream, never rewrite what was recorded."""
    store = EvidenceStore(tmp_path)
    history = [stamped(claim="old-1").model_dump(), stamped(claim="old-2").model_dump()]
    store.array.parent.mkdir(parents=True)
    store.array.write_text(json.dumps(history, indent=2) + "\n")
    before = store.array.read_text()
    store.append(stamped(claim="new"))
    assert [entry.claim for entry in store.read()] == ["old-1", "old-2", "new"]
    assert store.array.read_text() == before
    assert store.path.read_text() == stamped(claim="new").model_dump_json() + "\n"


def test_a_torn_array_element_costs_only_itself(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    store.array.parent.mkdir(parents=True)
    store.array.write_text(json.dumps([stamped(claim="kept").model_dump(), {"claim": "half"}]))
    with pytest.warns(TornLedger, match=r"\[2\] is not a certificate"):
        assert [entry.claim for entry in store.read()] == ["kept"]


@pytest.fixture
def broken_home(tmp_path: Path) -> Path:
    """An evidence directory holding three non-ledger files beside a real ledger."""
    home = tmp_path / "evidence"
    home.mkdir(parents=True)
    (home / "broken.json").write_text("{not json")
    (home / "shaped_wrong.json").write_text('["just", "strings"]')
    (home / "not_an_array.json").write_text('{"rows": []}')
    (home / "baselines.parquet").write_bytes(b"PAR1")
    EvidenceStore(tmp_path).append(stamped())
    return tmp_path


def test_ledgers_skip_and_strays_report_broken_files(broken_home: Path) -> None:
    with pytest.warns(TornLedger):
        assert set(EvidenceStore.ledgers(broken_home)) == {stamped().hostname}
    with pytest.warns(TornLedger):
        strays = {path.name for path in EvidenceStore.strays(broken_home)}
    assert strays == {"broken.json", "shaped_wrong.json", "not_an_array.json"}


def test_hosts_fold_the_two_formats_of_one_host_into_one_reading(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    store.array.parent.mkdir(parents=True)
    store.array.write_text(json.dumps([stamped(claim="old").model_dump()]))
    store.append(stamped(claim="new"))
    assert EvidenceStore.hosts(tmp_path) == [store.hostname]
    assert [entry.claim for entry in EvidenceStore.ledgers(tmp_path)[store.hostname]] == [
        "old",
        "new",
    ]


def test_newest_keeps_the_latest_word_on_each_claim_across_hosts(tmp_path: Path) -> None:
    """The lint's view: whoever ran a claim last is what the record currently says."""
    old = stamped(claim="demo/ok").model_copy(update={"timestamp": "2026-06-01T00:00:00.000000Z"})
    EvidenceStore(tmp_path).append(old)
    fresh = stamped(claim="demo/ok").model_copy(
        update={"hostname": "elsewhere", "timestamp": "2026-06-09T00:00:00.000000Z"}
    )
    EvidenceStore(tmp_path, hostname="elsewhere").append(fresh)
    latest = EvidenceStore.newest(tmp_path, "demo")
    assert set(latest) == {"ok"}
    assert latest["ok"].hostname == "elsewhere"


def test_newest_ignores_certificates_outside_the_slugs_own_claims(tmp_path: Path) -> None:
    EvidenceStore(tmp_path).append(stamped(claim="fit data.csv"))
    EvidenceStore(tmp_path).append(stamped(claim="other/ok"))
    assert EvidenceStore.newest(tmp_path, "demo") == {}


@given(st.lists(st.text(min_size=1, max_size=40), min_size=1, max_size=6))
def test_a_stream_line_is_always_one_whole_certificate(outputs: Sequence[str]) -> None:
    """Every appended line round-trips on its own, whatever text the result carries."""
    with tempfile.TemporaryDirectory() as directory:
        store = EvidenceStore(Path(directory))
        for index, output in enumerate(outputs):
            store.append(
                stamped(claim=f"demo/{index}").model_copy(update={"result": {"output": output}})
            )
        lines = store.path.read_text().split("\n")[:-1]
        assert [Certificate.model_validate_json(line).result for line in lines] == [
            {"output": output} for output in outputs
        ]

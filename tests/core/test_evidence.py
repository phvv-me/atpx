import json
import tempfile
from pathlib import Path
from threading import Barrier, Thread

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx import EvidenceStore
from atpx.core import EvidenceError

from ..support import stamped

claims = st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=5)
_WORKERS = 8


@given(claims)
def test_appends_accumulate_in_order(claims: list[str]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = EvidenceStore(Path(directory))
        for claim in claims:
            store.append(stamped(claim=claim))
        assert [entry.claim for entry in store.read()] == claims


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


def test_each_host_writes_only_its_own_file(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    path = store.append(stamped())
    assert path == tmp_path / "evidence" / f"{store.hostname}.json"


def test_a_foreign_certificate_is_refused(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path, hostname="elsewhere")
    with pytest.raises(EvidenceError, match="cannot enter"):
        store.append(stamped())


def test_a_ledger_holding_foreign_evidence_is_refused(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    foreign = stamped().model_copy(update={"hostname": "elsewhere"})
    store.path.parent.mkdir(parents=True)
    store.path.write_text(json.dumps([foreign.model_dump()]))
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


@pytest.fixture
def broken_home(tmp_path: Path) -> Path:
    """An evidence directory holding two non-ledger files beside a real ledger."""
    home = tmp_path / "evidence"
    home.mkdir(parents=True)
    (home / "broken.json").write_text("{not json")
    (home / "shaped_wrong.json").write_text('["just", "strings"]')
    EvidenceStore(tmp_path).append(stamped())
    return tmp_path


def test_ledgers_skip_and_strays_report_broken_files(broken_home: Path) -> None:
    assert set(EvidenceStore.ledgers(broken_home)) == {stamped().hostname}
    strays = {path.name for path in EvidenceStore.strays(broken_home)}
    assert strays == {"broken.json", "shaped_wrong.json"}
    with pytest.raises(EvidenceError, match="not a certificate ledger"):
        EvidenceStore(broken_home, hostname="broken").read()


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

import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from atpx.evidence import EvidenceError, EvidenceStore

from .conftest import stamped

claims = st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=5)


@given(claims)
def test_appends_accumulate_in_order(claims: list[str]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = EvidenceStore(Path(directory))
        for claim in claims:
            store.append(stamped(claim=claim))
        assert [entry.claim for entry in store.read()] == claims


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

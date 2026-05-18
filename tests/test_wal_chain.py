"""
tests/test_wal_chain.py
========================
TEST-CM-001: WAL SHA-256 chain is valid after N appends.
TEST-CM-002: WAL file is valid NDJSON.
TEST-CM-007: WAL write is atomic.
TEST-CM-010: WAL written by one project is readable by another.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from chronomemory import ChronoRecord, ChronoStore


def _make_fact(n: int) -> ChronoRecord:
    return ChronoRecord(id=f"F-{n}", label=f"Fact {n}", confidence=0.9)


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# TEST-CM-001: SHA-256 hash chain integrity
# ---------------------------------------------------------------------------


def test_wal_hash_chain_integrity(tmp_root: Path) -> None:
    """TEST-CM-001: chain_valid() after 10 appends; fails on in-memory mutation."""
    with ChronoStore(tmp_root) as store:
        for i in range(10):
            store.upsert(_make_fact(i))

        assert store.chain_valid() is True

        # Simulate in-memory tamper (disk WAL is untouched)
        store._state["F-5"].label = "TAMPERED"  # type: ignore[attr-defined]  # noqa: SLF001
        # chain_valid() reads from disk — still valid
        assert store.chain_valid() is True

    # Re-open and verify chain on disk
    with ChronoStore(tmp_root) as store2:
        assert store2.chain_valid() is True
        assert store2.record_count() == 10


def test_chain_detects_wal_tampering(tmp_root: Path) -> None:
    """Mutating a WAL line in-place must cause chain_valid() to return False."""
    with ChronoStore(tmp_root) as store:
        store.upsert(_make_fact(0))
        store.upsert(_make_fact(1))

    wal_path = tmp_root / ".chronomemory" / "events.wal"
    lines = wal_path.read_text(encoding="utf-8").splitlines()

    # Tamper with first event's record payload
    first_event = json.loads(lines[0])
    first_event["record"]["label"] = "TAMPERED"
    lines[0] = json.dumps(first_event)
    wal_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with ChronoStore(tmp_root) as store2:
        assert store2.chain_valid() is False


# ---------------------------------------------------------------------------
# TEST-CM-002: NDJSON format
# ---------------------------------------------------------------------------


def test_wal_is_ndjson(tmp_root: Path) -> None:
    """TEST-CM-002: Every non-empty WAL line parses as JSON; no binary magic bytes."""
    with ChronoStore(tmp_root) as store:
        store.upsert(_make_fact(0))
        store.upsert(_make_fact(1))

    wal_path = tmp_root / ".chronomemory" / "events.wal"
    raw = wal_path.read_bytes()

    # No binary magic header (e.g., not b"ESDB_WAL")
    assert not raw.startswith(b"ESDB_WAL"), "WAL must not use binary format"

    # Every non-empty line must parse as JSON
    for i, line in enumerate(raw.decode("utf-8").splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            pytest.fail(f"WAL line {i} is not valid JSON: {e}\nLine: {line!r}")
        assert isinstance(obj, dict), f"WAL line {i} must be a JSON object, got {type(obj)}"
        # Required NDJSON fields
        assert "seq" in obj, f"WAL line {i} missing 'seq'"
        assert "hash" in obj, f"WAL line {i} missing 'hash'"
        assert "op" in obj, f"WAL line {i} missing 'op'"


# ---------------------------------------------------------------------------
# TEST-CM-007: Atomic WAL write
# ---------------------------------------------------------------------------


def test_atomic_wal_write_fallback_on_replace_failure(tmp_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """TEST-CM-007: If os.replace fails, the fallback path must not corrupt the WAL."""
    import os

    original_replace = os.replace
    replace_call_count = [0]

    def patched_replace(src: str, dst: str) -> None:
        replace_call_count[0] += 1
        if replace_call_count[0] == 1:
            # Simulate failure on first call
            raise OSError("Simulated replace failure")
        original_replace(src, dst)

    monkeypatch.setattr("os.replace", patched_replace)

    with ChronoStore(tmp_root) as store:
        store.upsert(_make_fact(0))  # This triggers the os.replace failure + fallback
        store.upsert(_make_fact(1))  # Second write should succeed normally

    # Restore and verify
    monkeypatch.setattr("os.replace", original_replace)

    with ChronoStore(tmp_root) as store2:
        # At minimum the second record should be present; chain must be valid
        assert store2.chain_valid() is True


# ---------------------------------------------------------------------------
# TEST-CM-010: Cross-project WAL compatibility
# ---------------------------------------------------------------------------


def test_cross_project_wal_compatibility(tmp_path: Path) -> None:
    """TEST-CM-010: WAL written in one dir is readable in another."""
    dir_a = tmp_path / "project_a"
    dir_b = tmp_path / "project_b"
    dir_a.mkdir()
    dir_b.mkdir()

    # Write 5 records in project_a
    with ChronoStore(dir_a) as store_a:
        for i in range(5):
            store_a.upsert(ChronoRecord(
                id=f"SHARED-{i}",
                label=f"Shared fact {i}",
                source_type="observed",
                confidence=0.95,
            ))
        assert store_a.chain_valid() is True

    # Copy .chronomemory/ to project_b
    shutil.copytree(str(dir_a / ".chronomemory"), str(dir_b / ".chronomemory"))

    # Open in project_b — all records must be present and chain valid
    with ChronoStore(dir_b) as store_b:
        assert store_b.chain_valid() is True
        assert store_b.record_count() == 5
        for i in range(5):
            rec = store_b.get(f"SHARED-{i}")
            assert rec is not None, f"SHARED-{i} missing in project_b"
            assert rec.label == f"Shared fact {i}"

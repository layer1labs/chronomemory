"""
tests/test_store.py
===================
TEST-CM-004: Snapshot + WAL tail replay produces correct state.
TEST-CM-006: delete() tombstones record without physical removal.
TEST-CM-008: migrate_from_json() is idempotent.
TEST-CM-009: chronomemory imports without any external package installed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from chronomemory import ChronoRecord, ChronoStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_record(n: int) -> ChronoRecord:
    return ChronoRecord(
        id=f"FACT-{n:04d}",
        kind="fact",
        label=f"Test fact number {n}",
        confidence=0.9,
        source_type="observed",
        evidence=[f"test-run-{n}"],
    )


@pytest.fixture()
def tmp_root(tmp_path: Path) -> Path:
    return tmp_path


# ---------------------------------------------------------------------------
# TEST-CM-004: Snapshot + WAL tail replay
# ---------------------------------------------------------------------------


def test_snapshot_replay_consistency(tmp_root: Path) -> None:
    """TEST-CM-004: 55 records survive close + reopen with snapshot + tail replay."""
    with ChronoStore(tmp_root) as store:
        for i in range(55):
            store.upsert(make_record(i))
        assert store.wal_seq() == 55

    # Reopen — should load snapshot (written at seq 50) + replay 5-event tail
    with ChronoStore(tmp_root) as store2:
        assert store2.record_count() == 55
        assert store2.wal_seq() == 55

        # All records present
        for i in range(55):
            rec = store2.get(f"FACT-{i:04d}")
            assert rec is not None, f"Record FACT-{i:04d} missing after replay"
            assert rec.label == f"Test fact number {i}"


def test_corrupt_snapshot_falls_back_to_wal(tmp_root: Path) -> None:
    """Corrupt snapshot.json must not crash open(); WAL replay recovers state."""
    with ChronoStore(tmp_root) as store:
        for i in range(5):
            store.upsert(make_record(i))

    # Corrupt the snapshot
    snap = tmp_root / ".chronomemory" / "snapshot.json"
    snap.write_text("CORRUPT_DATA_NOT_JSON", encoding="utf-8")

    # Should recover from WAL
    with ChronoStore(tmp_root) as store2:
        assert store2.record_count() == 5


# ---------------------------------------------------------------------------
# TEST-CM-006: Tombstone semantics
# ---------------------------------------------------------------------------


def test_tombstone_no_physical_removal(tmp_root: Path) -> None:
    """TEST-CM-006: delete() tombstones, never physically removes."""
    with ChronoStore(tmp_root) as store:
        store.upsert(ChronoRecord(id="DEL-001", kind="fact", label="Will be deleted"))
        store.delete("DEL-001")

        # Record must still be gettable
        rec = store.get("DEL-001")
        assert rec is not None, "Tombstoned record must not disappear"
        assert rec.status == "tombstone"

        # Must not appear in active query
        active = store.query(status="active")
        assert not any(r.id == "DEL-001" for r in active)

    # Verify WAL has both events (upsert + delete)
    wal = (tmp_root / ".chronomemory" / "events.wal").read_text(encoding="utf-8")
    lines = [line for line in wal.splitlines() if line.strip()]
    assert len(lines) >= 2, "WAL must retain both upsert and delete events"


# ---------------------------------------------------------------------------
# TEST-CM-008: migrate_from_json idempotent
# ---------------------------------------------------------------------------


def test_migrate_from_json_idempotent(tmp_root: Path) -> None:
    """TEST-CM-008: migrate_from_json() is idempotent and maps governance status correctly."""
    specsmith_dir = tmp_root / ".specsmith"
    specsmith_dir.mkdir()

    requirements = [
        {"id": "REQ-001", "title": "First requirement", "status": "implemented", "confidence": 0.9},
        {"id": "REQ-002", "title": "Second requirement", "status": "defined", "confidence": 0.7},
    ]
    testcases = [
        {"id": "TEST-001", "title": "First test", "status": "active", "confidence": 1.0},
    ]
    (specsmith_dir / "requirements.json").write_text(json.dumps(requirements))
    (specsmith_dir / "testcases.json").write_text(json.dumps(testcases))

    with ChronoStore(tmp_root) as store:
        counts1 = store.migrate_from_json(specsmith_dir)
        assert counts1["requirements"] == 2
        assert counts1["testcases"] == 1

        # Run again — all should be skipped
        counts2 = store.migrate_from_json(specsmith_dir)
        assert counts2["skipped"] == 3

        # All records have source_type="observed"
        for rec in store.query():
            assert rec.source_type == "observed", f"{rec.id} missing source_type=observed"

        # Governance status "implemented" → ESDB status "active"
        req1 = store.get("REQ-001")
        assert req1 is not None
        assert req1.status == "active", "Governance 'implemented' must map to ESDB 'active'"

        # record count must equal unique IDs
        assert store.record_count() == 3


# ---------------------------------------------------------------------------
# TEST-CM-009: Zero external dependencies
# ---------------------------------------------------------------------------


def test_zero_external_deps() -> None:
    """TEST-CM-009: chronomemory imports with no third-party packages.

    Two checks:
    1. pyproject.toml declares no runtime dependencies.
    2. A subprocess with -S (no site-packages) + PYTHONPATH pointing only at
       our src/ can import chronomemory successfully.  This proves the package
       needs no third-party package from site-packages.
    """
    import os

    # Check 1: pyproject.toml must have empty dependencies list
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    assert "dependencies = []" in text, (
        "pyproject.toml must declare an empty dependencies list (REQ-CM-009)"
    )

    # Check 2: import succeeds with -S (site-packages disabled)
    src_dir = str(Path(__file__).parent.parent / "src")
    code = (
        "from chronomemory import ChronoStore, ChronoRecord, WalEvent, EsdbBridge; "
        "print('OK')"
    )
    env = {**os.environ, "PYTHONPATH": src_dir}
    result = subprocess.run(
        [sys.executable, "-S", "-c", code],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, (
        f"Import failed with -S (no site-packages):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout

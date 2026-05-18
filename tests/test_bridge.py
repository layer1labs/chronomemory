"""
tests/test_bridge.py
====================
Tests for EsdbBridge: unified read/write adapter with ChronoStore delegation
and .specsmith/ JSON fallback.
"""

from __future__ import annotations

import json
from pathlib import Path

from chronomemory import ChronoRecord, ChronoStore, EsdbBridge
from chronomemory.bridge import EsdbRecord, EsdbStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_specsmith_dir(
    root: Path, requirements: list[dict], testcases: list[dict] | None = None
) -> Path:
    sm = root / ".specsmith"
    sm.mkdir(exist_ok=True)
    (sm / "requirements.json").write_text(json.dumps(requirements), encoding="utf-8")
    if testcases is not None:
        (sm / "testcases.json").write_text(json.dumps(testcases), encoding="utf-8")
    return sm


def _populate_store(root: Path, n: int = 3) -> None:
    with ChronoStore(root) as s:
        for i in range(n):
            s.upsert(
                ChronoRecord(
                    id=f"REC-{i:03d}",
                    kind="requirement" if i % 2 == 0 else "testcase",
                    label=f"Record {i}",
                    confidence=0.9,
                    source_type="observed",
                )
            )


# ===========================================================================
# 1. Status
# ===========================================================================


class TestEsdbBridgeStatus:
    def test_status_with_wal_backend(self, tmp_path: Path) -> None:
        """status() reports ChronoStore WAL backend when .chronomemory/events.wal exists."""
        _populate_store(tmp_path, 5)
        bridge = EsdbBridge(project_dir=str(tmp_path))
        status = bridge.status()

        assert isinstance(status, EsdbStatus)
        assert status.available is True
        assert "ChronoStore" in status.backend or "WAL" in status.backend
        assert status.record_count == 5
        assert status.chain_valid is True
        assert status.wal_seq == 5

    def test_status_with_json_fallback(self, tmp_path: Path) -> None:
        """status() reports JSON fallback when no WAL exists but .specsmith/ does."""
        _make_specsmith_dir(
            tmp_path,
            [
                {"id": "REQ-001", "title": "Req", "confidence": 0.9},
            ],
            [
                {"id": "TEST-001", "title": "Test", "confidence": 1.0},
            ],
        )

        bridge = EsdbBridge(project_dir=str(tmp_path))
        status = bridge.status()

        assert status.available is True
        assert "json" in status.backend.lower() or "specsmith" in status.backend.lower()
        assert status.record_count == 2

    def test_status_empty_project(self, tmp_path: Path) -> None:
        """status() on completely empty project: available=True, record_count=0."""
        bridge = EsdbBridge(project_dir=str(tmp_path))
        status = bridge.status()
        assert status.available is True

    def test_status_to_dict(self, tmp_path: Path) -> None:
        """EsdbStatus.to_dict() returns expected keys."""
        _populate_store(tmp_path, 2)
        bridge = EsdbBridge(project_dir=str(tmp_path))
        d = bridge.status().to_dict()

        assert "available" in d
        assert "backend" in d
        assert "record_count" in d
        assert "wal_seq" in d
        assert "chain_valid" in d


# ===========================================================================
# 2. Requirements and test cases
# ===========================================================================


class TestEsdbBridgeQuery:
    def test_requirements_from_wal(self, tmp_path: Path) -> None:
        """requirements() returns requirement records from ChronoStore WAL."""
        with ChronoStore(tmp_path) as s:
            s.upsert(
                ChronoRecord(id="REQ-001", kind="requirement", label="First req", confidence=0.9)
            )
            s.upsert(
                ChronoRecord(id="REQ-002", kind="requirement", label="Second req", confidence=0.8)
            )
            s.upsert(ChronoRecord(id="FACT-001", kind="fact", label="Not a req", confidence=0.9))

        bridge = EsdbBridge(project_dir=str(tmp_path))
        reqs = bridge.requirements()

        assert len(reqs) == 2
        ids = {r.id for r in reqs}
        assert "REQ-001" in ids
        assert "REQ-002" in ids
        assert "FACT-001" not in ids

    def test_testcases_from_wal(self, tmp_path: Path) -> None:
        """testcases() returns testcase records from ChronoStore WAL."""
        with ChronoStore(tmp_path) as s:
            s.upsert(
                ChronoRecord(id="TEST-001", kind="testcase", label="First test", confidence=1.0)
            )
            s.upsert(
                ChronoRecord(id="REQ-001", kind="requirement", label="Not a test", confidence=0.9)
            )

        bridge = EsdbBridge(project_dir=str(tmp_path))
        tests = bridge.testcases()

        assert len(tests) == 1
        assert tests[0].id == "TEST-001"

    def test_requirements_from_json_fallback(self, tmp_path: Path) -> None:
        """requirements() falls back to .specsmith/requirements.json when no WAL."""
        _make_specsmith_dir(
            tmp_path,
            [
                {"id": "REQ-JSON-001", "title": "JSON req 1", "confidence": 0.9},
                {"id": "REQ-JSON-002", "title": "JSON req 2", "confidence": 0.7},
            ],
        )

        bridge = EsdbBridge(project_dir=str(tmp_path))
        reqs = bridge.requirements()

        assert len(reqs) == 2
        ids = {r.id for r in reqs}
        assert "REQ-JSON-001" in ids
        assert "REQ-JSON-002" in ids

    def test_testcases_from_json_fallback(self, tmp_path: Path) -> None:
        """testcases() falls back to .specsmith/testcases.json when no WAL."""
        _make_specsmith_dir(
            tmp_path,
            [],
            [
                {"id": "TEST-JSON-001", "title": "JSON test 1", "confidence": 1.0},
            ],
        )

        bridge = EsdbBridge(project_dir=str(tmp_path))
        tests = bridge.testcases()

        assert len(tests) == 1
        assert tests[0].id == "TEST-JSON-001"

    def test_empty_requirements(self, tmp_path: Path) -> None:
        """requirements() returns [] when no records or fallback files."""
        bridge = EsdbBridge(project_dir=str(tmp_path))
        assert bridge.requirements() == []

    def test_record_counts_by_kind(self, tmp_path: Path) -> None:
        """record_counts() returns dict mapping kind → count."""
        with ChronoStore(tmp_path) as s:
            for i in range(3):
                s.upsert(ChronoRecord(id=f"REQ-{i}", kind="requirement", label=f"Req {i}"))
            for i in range(2):
                s.upsert(ChronoRecord(id=f"TC-{i}", kind="testcase", label=f"Test {i}"))
            s.upsert(ChronoRecord(id="FACT-1", kind="fact", label="A fact"))

        bridge = EsdbBridge(project_dir=str(tmp_path))
        counts = bridge.record_counts()

        assert counts.get("requirement", 0) == 3
        assert counts.get("testcase", 0) == 2
        assert counts.get("fact", 0) == 1

    def test_record_counts_json_fallback(self, tmp_path: Path) -> None:
        """record_counts() from JSON fallback returns requirements and testcases counts."""
        _make_specsmith_dir(
            tmp_path,
            [
                {"id": "R1"},
                {"id": "R2"},
            ],
            [
                {"id": "T1"},
            ],
        )

        bridge = EsdbBridge(project_dir=str(tmp_path))
        counts = bridge.record_counts()

        assert counts.get("requirements", 0) == 2
        assert counts.get("testcases", 0) == 1


# ===========================================================================
# 3. Write operations
# ===========================================================================


class TestEsdbBridgeWrite:
    def test_upsert_record_via_bridge(self, tmp_path: Path) -> None:
        """upsert_record() writes through to ChronoStore when WAL exists."""
        # Ensure WAL exists (even empty)
        with ChronoStore(tmp_path) as s:
            pass  # Creates the .chronomemory dir + empty WAL on first write

        # Seed with one record to ensure WAL is initialized
        with ChronoStore(tmp_path) as s:
            s.upsert(ChronoRecord(id="SEED", label="seed"))

        bridge = EsdbBridge(project_dir=str(tmp_path))
        rec = EsdbRecord(id="BRIDGE-001", kind="fact", label="Via bridge", confidence=0.85)
        result = bridge.upsert_record(rec)
        assert result is True

        # Verify it's readable via direct ChronoStore
        with ChronoStore(tmp_path) as s:
            loaded = s.get("BRIDGE-001")
            assert loaded is not None
            assert loaded.label == "Via bridge"

    def test_upsert_returns_false_without_wal(self, tmp_path: Path) -> None:
        """upsert_record() returns False when no WAL exists (JSON fallback only)."""
        bridge = EsdbBridge(project_dir=str(tmp_path))
        rec = EsdbRecord(id="NOOP", kind="fact", label="No WAL")
        result = bridge.upsert_record(rec)
        assert result is False

    def test_delete_record_via_bridge(self, tmp_path: Path) -> None:
        """delete_record() tombstones via ChronoStore when WAL exists."""
        with ChronoStore(tmp_path) as s:
            s.upsert(ChronoRecord(id="DEL-ME", label="Will be deleted"))

        bridge = EsdbBridge(project_dir=str(tmp_path))
        result = bridge.delete_record("DEL-ME")
        assert result is True

        with ChronoStore(tmp_path) as s:
            rec = s.get("DEL-ME")
            assert rec is not None
            assert rec.status == "tombstone"

    def test_delete_returns_false_without_wal(self, tmp_path: Path) -> None:
        """delete_record() returns False when no WAL exists."""
        bridge = EsdbBridge(project_dir=str(tmp_path))
        result = bridge.delete_record("WHATEVER")
        assert result is False


# ===========================================================================
# 4. EsdbRecord
# ===========================================================================


class TestEsdbRecord:
    def test_to_dict_with_data(self) -> None:
        """EsdbRecord.to_dict() returns data if set."""
        rec = EsdbRecord(id="X", kind="fact", label="Test", data={"key": "val"})
        d = rec.to_dict()
        assert d["key"] == "val"

    def test_to_dict_without_data_uses_fields(self) -> None:
        """EsdbRecord.to_dict() returns field dict when data is empty."""
        rec = EsdbRecord(id="X", kind="fact", label="Test")
        d = rec.to_dict()
        assert d["id"] == "X"
        assert d["kind"] == "fact"
        assert d["label"] == "Test"

    def test_esdb_record_defaults(self) -> None:
        """EsdbRecord has safe defaults for optional fields."""
        rec = EsdbRecord(id="MIN")
        assert rec.kind == "fact"
        assert rec.status == "active"
        assert rec.confidence == 0.7
        assert rec.label == ""
        assert rec.data == {}
        assert rec.source_ids == []

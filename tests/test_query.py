"""
tests/test_query.py
====================
TEST-CM-005: query(rag_filter=True) applies H18 confidence threshold.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from chronomemory import ChronoRecord, ChronoStore


@pytest.fixture()
def populated_store(tmp_path: Path) -> ChronoStore:
    store = ChronoStore(tmp_path).open()
    store.upsert(ChronoRecord(
        id="HIGH", kind="fact", confidence=0.9, status="active", label="High conf"
    ))
    store.upsert(ChronoRecord(
        id="THRESHOLD", kind="fact", confidence=0.6, status="active", label="At threshold"
    ))
    store.upsert(ChronoRecord(
        id="LOW", kind="fact", confidence=0.5, status="active", label="Low conf"
    ))
    store.upsert(ChronoRecord(
        id="ZERO", kind="fact", confidence=0.0, status="active", label="Zero conf"
    ))
    store.upsert(ChronoRecord(
        id="TOMBED", kind="fact", confidence=0.9, status="tombstone", label="Tombstoned"
    ))
    store.upsert(ChronoRecord(
        id="REQ", kind="requirement", confidence=0.95, status="active", label="A requirement"
    ))
    return store


def test_rag_filter_confidence_threshold(populated_store: ChronoStore) -> None:
    """TEST-CM-005: rag_filter=True returns only confidence >= 0.6 AND status=active."""
    results = populated_store.query(rag_filter=True)
    ids = {r.id for r in results}

    assert "HIGH" in ids,      "HIGH (0.9, active) must be included"
    assert "THRESHOLD" in ids, "THRESHOLD (0.6, active) must be included"
    assert "REQ" in ids,       "REQ (0.95, active) must be included"
    assert "LOW" not in ids,   "LOW (0.5) must be excluded"
    assert "ZERO" not in ids,  "ZERO (0.0) must be excluded"
    assert "TOMBED" not in ids, "TOMBED (tombstone) must be excluded even at 0.9"
    populated_store.close()


def test_query_by_kind(populated_store: ChronoStore) -> None:
    """query(kind='requirement') returns only records of that kind."""
    results = populated_store.query(kind="requirement")
    assert len(results) == 1
    assert results[0].id == "REQ"
    populated_store.close()


def test_query_min_confidence_override(populated_store: ChronoStore) -> None:
    """min_confidence=0.95 must exclude HIGH (0.9) and include REQ (0.95)."""
    results = populated_store.query(min_confidence=0.95)
    ids = {r.id for r in results}
    # HIGH has confidence 0.9 which is < 0.95 — must be excluded
    assert "HIGH" not in ids, "HIGH (0.9) should be excluded at min_confidence=0.95"
    assert "REQ" in ids, "REQ (0.95) must be included at min_confidence=0.95"
    assert "LOW" not in ids
    assert "ZERO" not in ids
    populated_store.close()


def test_query_all_active_by_default(populated_store: ChronoStore) -> None:
    """query() with no filters returns all active records."""
    results = populated_store.query()
    ids = {r.id for r in results}
    assert "TOMBED" not in ids, "Default query excludes tombstoned records"
    assert len(results) == 5   # HIGH, THRESHOLD, LOW, ZERO, REQ
    populated_store.close()


def test_query_include_all_statuses(populated_store: ChronoStore) -> None:
    """query(status='') returns records of any status."""
    results = populated_store.query(status="")
    ids = {r.id for r in results}
    assert "TOMBED" in ids
    populated_store.close()


def test_get_by_id(populated_store: ChronoStore) -> None:
    """get() returns correct record or None."""
    rec = populated_store.get("HIGH")
    assert rec is not None
    assert rec.confidence == 0.9

    missing = populated_store.get("DOES_NOT_EXIST")
    assert missing is None
    populated_store.close()

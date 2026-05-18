"""
tests/test_oea.py
=================
TEST-CM-003: ChronoRecord carries all 7 OEA anti-hallucination fields.
"""

from __future__ import annotations

from pathlib import Path

from chronomemory import ChronoRecord, ChronoStore

OEA_FIELDS = [
    "source_type",
    "confidence",
    "evidence",
    "epistemic_boundary",
    "is_hypothesis",
    "model_assumptions",
    "recursion_depth",
]


def test_all_oea_fields_present() -> None:
    """TEST-CM-003: ChronoRecord.to_dict() contains all 7 OEA fields."""
    rec = ChronoRecord(id="OEA-001", label="Test record")
    d = rec.to_dict()

    for field in OEA_FIELDS:
        assert field in d, f"OEA field '{field}' missing from ChronoRecord.to_dict()"


def test_oea_fields_have_correct_types() -> None:
    """OEA fields must have the types specified in ESDB-Specification §3."""
    rec = ChronoRecord(
        id="OEA-002",
        label="Typed test",
        source_type="inferred",
        confidence=0.8,
        evidence=["source-a", "source-b"],
        epistemic_boundary=["domain:cpsc"],
        is_hypothesis=True,
        model_assumptions={"provider": "openai", "temperature": 0.7},
        recursion_depth=2,
    )

    assert isinstance(rec.source_type, str)
    assert isinstance(rec.confidence, float)
    assert isinstance(rec.evidence, list)
    assert isinstance(rec.epistemic_boundary, list)
    assert isinstance(rec.is_hypothesis, bool)
    assert isinstance(rec.model_assumptions, dict)
    assert isinstance(rec.recursion_depth, int)


def test_oea_safe_defaults() -> None:
    """Records created with minimal fields must have safe OEA defaults."""
    rec = ChronoRecord(id="MIN-001")

    assert rec.source_type == "observed"
    assert rec.confidence == 0.7
    assert rec.evidence == []
    assert rec.epistemic_boundary == []
    assert rec.is_hypothesis is False
    assert rec.model_assumptions == {}
    assert rec.recursion_depth == 0


def test_oea_fields_survive_wal_roundtrip(tmp_path: Path) -> None:
    """TEST-CM-003: OEA fields must survive upsert() + WAL replay."""
    rec = ChronoRecord(
        id="ROUND-001",
        label="Roundtrip test",
        source_type="synthetic",
        confidence=0.65,
        evidence=["gpt-4o", "prompt-v3"],
        epistemic_boundary=["project:chronoagent"],
        is_hypothesis=False,
        model_assumptions={"provider": "openai", "context_window": 128000, "temperature": 0.0},
    )

    # recursion_depth=1 is stamped by the store (H16), not by the record at construction.
    with ChronoStore(tmp_path, recursion_depth=1) as store:
        store.upsert(rec)

    # Reload from WAL
    with ChronoStore(tmp_path) as store2:
        loaded = store2.get("ROUND-001")
        assert loaded is not None

        assert loaded.source_type == "synthetic"
        assert abs(loaded.confidence - 0.65) < 1e-9
        assert loaded.evidence == ["gpt-4o", "prompt-v3"]
        assert loaded.epistemic_boundary == ["project:chronoagent"]
        assert loaded.is_hypothesis is False
        assert loaded.model_assumptions["provider"] == "openai"
        assert loaded.recursion_depth == 1


def test_recursion_depth_set_by_store(tmp_path: Path) -> None:
    """ChronoStore(recursion_depth=N) must stamp N on every upserted record (H16)."""
    rec = ChronoRecord(id="DEPTH-001", label="Depth test")

    with ChronoStore(tmp_path, recursion_depth=3) as store:
        store.upsert(rec)
        loaded = store.get("DEPTH-001")
        assert loaded is not None
        assert loaded.recursion_depth == 3


def test_passes_rag_filter_respects_h18() -> None:
    """passes_rag_filter() must implement H18: confidence >= 0.6 AND status == active."""
    active_high = ChronoRecord(id="A", confidence=0.9, status="active")
    active_threshold = ChronoRecord(id="B", confidence=0.6, status="active")
    active_low = ChronoRecord(id="C", confidence=0.5, status="active")
    tombstone_high = ChronoRecord(id="D", confidence=0.9, status="tombstone")

    assert active_high.passes_rag_filter() is True
    assert active_threshold.passes_rag_filter() is True
    assert active_low.passes_rag_filter() is False
    assert tombstone_high.passes_rag_filter() is False

"""tests/test_rollback.py — Epistemic rollback unit tests (Issue #2, ≥8 tests)."""

from __future__ import annotations

from pathlib import Path

import pytest

from chronomemory import ChronoRecord, ChronoStore, DepGraph
from chronomemory.rollback import RollbackReport, invalidate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> ChronoStore:
    s = ChronoStore(tmp_path).open()
    s.upsert(ChronoRecord(id="FACT-A", kind="fact", label="root fact", confidence=0.9))
    s.upsert(ChronoRecord(id="FACT-B", kind="fact", label="depends on A", confidence=0.8))
    s.upsert(ChronoRecord(id="FACT-C", kind="fact", label="derived from B", confidence=0.7))
    return s


@pytest.fixture()
def graph() -> DepGraph:
    g = DepGraph()
    g.add_edge("FACT-B", "FACT-A", "depends_on")
    g.add_edge("FACT-C", "FACT-B", "derived_from")
    return g


# ---------------------------------------------------------------------------
# Tests: direct invalidation
# ---------------------------------------------------------------------------


def test_invalidate_marks_target_as_invalidated(store: ChronoStore, graph: DepGraph) -> None:
    """invalidate sets the target record's status to 'invalidated'."""
    report = invalidate("FACT-A", "test reason", store, graph)
    updated = store.get("FACT-A")
    assert updated is not None
    assert updated.status == "invalidated"
    assert report.target_id == "FACT-A"
    assert report.direct_change is not None
    assert report.direct_change.new_status == "invalidated"


def test_invalidate_missing_record_returns_report(store: ChronoStore, graph: DepGraph) -> None:
    """invalidate on a non-existent record returns a report with no direct_change."""
    report = invalidate("NONEXISTENT", "test", store, graph)
    assert report.direct_change is None
    assert report.target_id == "NONEXISTENT"


# ---------------------------------------------------------------------------
# Tests: cascade propagation
# ---------------------------------------------------------------------------


def test_cascade_one_level(store: ChronoStore, graph: DepGraph) -> None:
    """Invalidating FACT-A cascades to FACT-B (depends_on)."""
    report = invalidate("FACT-A", "cascade test", store, graph)
    fact_b = store.get("FACT-B")
    assert fact_b is not None
    assert fact_b.status == "hypothesis"
    assert fact_b.is_hypothesis is True
    cascaded_ids = [c.record_id for c in report.cascaded]
    assert "FACT-B" in cascaded_ids


def test_cascade_two_levels(store: ChronoStore, graph: DepGraph) -> None:
    """Invalidating FACT-A cascades 2-deep: FACT-B and FACT-C both downgraded."""
    report = invalidate("FACT-A", "deep cascade", store, graph)
    fact_c = store.get("FACT-C")
    assert fact_c is not None
    assert fact_c.status == "hypothesis"
    cascaded_ids = [c.record_id for c in report.cascaded]
    assert "FACT-C" in cascaded_ids


def test_cascade_halves_confidence(store: ChronoStore, graph: DepGraph) -> None:
    """Cascaded records have their confidence halved."""
    invalidate("FACT-A", "conf test", store, graph)
    fact_b = store.get("FACT-B")
    assert fact_b is not None
    assert fact_b.confidence == pytest.approx(0.4)  # 0.8 * 0.5


def test_affected_ids_includes_all(store: ChronoStore, graph: DepGraph) -> None:
    """RollbackReport.affected_ids includes target + all cascaded IDs."""
    report = invalidate("FACT-A", "affected test", store, graph)
    assert "FACT-A" in report.affected_ids
    assert "FACT-B" in report.affected_ids
    assert "FACT-C" in report.affected_ids


# ---------------------------------------------------------------------------
# Tests: circular dependency guard
# ---------------------------------------------------------------------------


def test_circular_dependency_does_not_loop(tmp_path: Path) -> None:
    """invalidate handles circular graphs without infinite loop."""
    store = ChronoStore(tmp_path).open()
    store.upsert(ChronoRecord(id="X", kind="fact", label="x"))
    store.upsert(ChronoRecord(id="Y", kind="fact", label="y"))
    g = DepGraph()
    g.add_edge("Y", "X", "depends_on")
    g.add_edge("X", "Y", "depends_on")  # circular
    # Must terminate without error
    report = invalidate("X", "circular test", store, g)
    assert report is not None


# ---------------------------------------------------------------------------
# Tests: WAL record written
# ---------------------------------------------------------------------------


def test_rollback_event_written_to_wal(store: ChronoStore, graph: DepGraph) -> None:
    """invalidate writes a rollback_event record to the WAL."""
    invalidate("FACT-A", "wal test", store, graph)
    rollback_rec = store.get("ROLLBACK-FACT-A")
    assert rollback_rec is not None
    assert rollback_rec.kind == "rollback_event"
    assert "FACT-A" in rollback_rec.data.get("target_id", "")


def test_chain_valid_after_rollback(store: ChronoStore, graph: DepGraph) -> None:
    """chain_valid() remains True after rollback operations."""
    invalidate("FACT-A", "chain test", store, graph)
    assert store.chain_valid()


# ---------------------------------------------------------------------------
# Tests: store convenience method
# ---------------------------------------------------------------------------


def test_store_invalidate_method(tmp_path: Path) -> None:
    """ChronoStore.invalidate() delegates correctly to rollback.invalidate."""
    store = ChronoStore(tmp_path).open()
    store.upsert(ChronoRecord(id="FACT-Z", kind="fact", label="z"))
    g = DepGraph()
    report = store.invalidate("FACT-Z", "method test", g)
    assert isinstance(report, RollbackReport)
    assert store.get("FACT-Z").status == "invalidated"  # type: ignore[union-attr]

"""tests/test_deps.py — DepGraph unit tests (Issue #1, ≥10 tests)."""

from __future__ import annotations

from pathlib import Path

import pytest

from chronomemory import ChronoRecord, ChronoStore, DependencyEdge, DepGraph
from chronomemory.deps import EDGE_TYPES

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> ChronoStore:
    return ChronoStore(tmp_path).open()


@pytest.fixture()
def graph() -> DepGraph:
    return DepGraph()


# ---------------------------------------------------------------------------
# Tests: construction and constants
# ---------------------------------------------------------------------------


def test_edge_types_is_frozenset() -> None:
    """EDGE_TYPES is a frozenset with all 9 required types."""
    assert isinstance(EDGE_TYPES, frozenset)
    for et in [
        "assumes",
        "contradicts",
        "depends_on",
        "derived_from",
        "generated_from",
        "invalidates",
        "supports",
        "supersedes",
        "validated_by",
    ]:
        assert et in EDGE_TYPES


def test_dep_graph_starts_empty(graph: DepGraph) -> None:
    """Newly constructed DepGraph has zero edges."""
    assert graph.edge_count() == 0
    assert graph.edges() == []


# ---------------------------------------------------------------------------
# Tests: add_edge / remove_edge
# ---------------------------------------------------------------------------


def test_add_edge_valid(graph: DepGraph) -> None:
    """add_edge stores the edge in memory."""
    graph.add_edge("A", "B", "depends_on")
    assert graph.edge_count() == 1
    edges = graph.edges()
    assert edges[0] == DependencyEdge("A", "B", "depends_on")


def test_add_edge_invalid_type_raises(graph: DepGraph) -> None:
    """add_edge with unknown edge_type raises ValueError."""
    with pytest.raises(ValueError, match="Unknown edge type"):
        graph.add_edge("A", "B", "blah_blah")


def test_remove_edge(graph: DepGraph) -> None:
    """remove_edge deletes an existing edge; no-op for missing edge."""
    graph.add_edge("A", "B", "depends_on")
    graph.remove_edge("A", "B", "depends_on")
    assert graph.edge_count() == 0
    # No-op for non-existent
    graph.remove_edge("X", "Y", "supports")  # should not raise


def test_add_multiple_edges(graph: DepGraph) -> None:
    """Multiple distinct edges are all stored."""
    graph.add_edge("A", "B", "depends_on")
    graph.add_edge("A", "C", "assumes")
    graph.add_edge("B", "C", "contradicts")
    assert graph.edge_count() == 3


# ---------------------------------------------------------------------------
# Tests: query operations
# ---------------------------------------------------------------------------


def test_what_depends_on(graph: DepGraph) -> None:
    """what_depends_on returns predecessors via depends_on edges."""
    graph.add_edge("CHILD", "PARENT", "depends_on")
    assert graph.what_depends_on("PARENT") == ["CHILD"]
    assert graph.what_depends_on("CHILD") == []


def test_what_contradicts_bidirectional(graph: DepGraph) -> None:
    """what_contradicts is bidirectional."""
    graph.add_edge("A", "B", "contradicts")
    assert "B" in graph.what_contradicts("A")
    assert "A" in graph.what_contradicts("B")


def test_what_assumes(graph: DepGraph) -> None:
    """what_assumes returns outgoing assumes edges from a record."""
    graph.add_edge("PLAN", "ASSUMPTION", "assumes")
    assert graph.what_assumes("PLAN") == ["ASSUMPTION"]
    assert graph.what_assumes("ASSUMPTION") == []


def test_transitive_successors_linear_chain(graph: DepGraph) -> None:
    """transitive_successors follows chains correctly."""
    graph.add_edge("A", "B", "depends_on")
    graph.add_edge("B", "C", "depends_on")
    result = graph.transitive_successors("A", frozenset(["depends_on"]))
    assert result == {"B", "C"}


def test_transitive_successors_circular_guard(graph: DepGraph) -> None:
    """transitive_successors does not loop on circular dependencies."""
    graph.add_edge("A", "B", "depends_on")
    graph.add_edge("B", "A", "depends_on")
    result = graph.transitive_successors("A", frozenset(["depends_on"]))
    assert "B" in result
    assert len(result) <= 2  # does not infinite-loop


# ---------------------------------------------------------------------------
# Tests: WAL persistence
# ---------------------------------------------------------------------------


def test_add_edge_persists_to_wal(tmp_path: Path) -> None:
    """Edges added with a store are persisted as kind='edge' WAL records."""
    with ChronoStore(tmp_path) as store:
        g = DepGraph(store=store)
        g.add_edge("REQ-001", "TEST-001", "validated_by")
        edge_rec = store.get("EDGE-REQ-001-TEST-001-validated_by")
        assert edge_rec is not None
        assert edge_rec.kind == "edge"
        assert edge_rec.data["from_id"] == "REQ-001"


def test_from_store_reloads_edges(tmp_path: Path) -> None:
    """DepGraph.from_store loads persisted edges from WAL."""
    with ChronoStore(tmp_path) as store:
        g = DepGraph(store=store)
        g.add_edge("A", "B", "supports")

    # Re-open and reload
    with ChronoStore(tmp_path) as store2:
        g2 = DepGraph.from_store(store2)
        assert g2.edge_count() == 1
        assert g2.edges()[0] == DependencyEdge("A", "B", "supports")


def test_chain_valid_covers_edge_events(tmp_path: Path) -> None:
    """chain_valid() returns True after adding edges (they go through normal WAL upsert)."""
    with ChronoStore(tmp_path) as store:
        store.upsert(ChronoRecord(id="R1", kind="fact", label="root fact"))
        g = DepGraph(store=store)
        g.add_edge("R1", "R2", "invalidates")
        assert store.chain_valid()

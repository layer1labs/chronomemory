# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Layer1Labs Silicon, Inc. / BitConcepts, LLC.
"""DepGraph — typed dependency graph between ESDB records.

Phase 2 / Issue #1: Dependency graph engine
Spec: ESDB Master Spec §13

Edges are stored as ChronoRecord(kind="edge") via the normal WAL upsert
path so they survive replay and are covered by chain_valid() automatically.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chronomemory.store import ChronoStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: All valid typed edge types per spec §13.
EDGE_TYPES: frozenset[str] = frozenset(
    [
        "assumes",
        "contradicts",
        "depends_on",
        "derived_from",
        "generated_from",
        "invalidates",
        "supports",
        "supersedes",
        "validated_by",
    ]
)


# ---------------------------------------------------------------------------
# DependencyEdge dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DependencyEdge:
    """A single typed directed edge between two records."""

    from_id: str
    to_id: str
    edge_type: str

    def to_dict(self) -> dict[str, Any]:
        return {"from_id": self.from_id, "to_id": self.to_id, "edge_type": self.edge_type}

    @classmethod
    def edge_id(cls, from_id: str, to_id: str, edge_type: str) -> str:
        """Canonical WAL record ID for an edge."""
        return f"EDGE-{from_id}-{to_id}-{edge_type}"


# ---------------------------------------------------------------------------
# DepGraph
# ---------------------------------------------------------------------------


class DepGraph:
    """In-memory dependency graph with optional WAL persistence.

    When constructed with a ``store``, every :py:meth:`add_edge` and
    :py:meth:`remove_edge` call is persisted as a ``ChronoRecord(kind="edge")``
    via the normal WAL upsert path, so:

    * edges survive WAL replay automatically (``_replay_wal`` picks them up)
    * ``chain_valid()`` covers them without any special handling

    Usage (in-memory only)::

        g = DepGraph()
        g.add_edge("REQ-001", "TEST-001", "validated_by")

    Usage (with WAL persistence)::

        with ChronoStore(root) as store:
            g = DepGraph(store=store)
            g.add_edge("FACT-001", "PLAN-001", "depends_on")
            # or load existing edges:
            g2 = DepGraph.from_store(store)
    """

    def __init__(self, store: ChronoStore | None = None) -> None:
        self._store = store
        # key: (from_id, to_id, edge_type) → DependencyEdge
        self._edges: dict[tuple[str, str, str], DependencyEdge] = {}

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_store(cls, store: ChronoStore) -> DepGraph:
        """Load a DepGraph by replaying all edge records from the store."""
        g = cls(store=store)
        for rec in store.query(kind="edge", status=""):
            if rec.status == "tombstone":
                continue
            from_id = rec.data.get("from_id", "")
            to_id = rec.data.get("to_id", "")
            edge_type = rec.data.get("edge_type", "")
            if from_id and to_id and edge_type:
                key = (from_id, to_id, edge_type)
                g._edges[key] = DependencyEdge(from_id, to_id, edge_type)
        return g

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        """Add a typed dependency edge.

        Persists to WAL as ``ChronoRecord(kind="edge")`` when a store is set.

        Args:
            from_id: Source record ID.
            to_id: Target record ID.
            edge_type: One of the valid EDGE_TYPES.

        Raises:
            ValueError: If edge_type is not in EDGE_TYPES.
        """
        if edge_type not in EDGE_TYPES:
            raise ValueError(f"Unknown edge type {edge_type!r}. Valid types: {sorted(EDGE_TYPES)}")
        key = (from_id, to_id, edge_type)
        self._edges[key] = DependencyEdge(from_id, to_id, edge_type)
        if self._store is not None:
            self._persist_edge(from_id, to_id, edge_type, active=True)

    def remove_edge(self, from_id: str, to_id: str, edge_type: str) -> None:
        """Remove a typed dependency edge (tombstones WAL record if store is set)."""
        key = (from_id, to_id, edge_type)
        self._edges.pop(key, None)
        if self._store is not None:
            edge_id = DependencyEdge.edge_id(from_id, to_id, edge_type)
            self._store.delete(edge_id)

    # ------------------------------------------------------------------
    # Query operations (spec §13)
    # ------------------------------------------------------------------

    def what_depends_on(self, record_id: str) -> list[str]:
        """Return IDs of all records that have a ``depends_on`` edge TO record_id."""
        return [
            from_id
            for (from_id, to_id, et) in self._edges
            if to_id == record_id and et == "depends_on"
        ]

    def what_contradicts(self, record_id: str) -> list[str]:
        """Return IDs of all records connected by a ``contradicts`` edge to record_id.

        Contradicts edges are treated as bidirectional for detection purposes.
        """
        result: list[str] = []
        for from_id, to_id, et in self._edges:
            if et == "contradicts":
                if from_id == record_id:
                    result.append(to_id)
                elif to_id == record_id:
                    result.append(from_id)
        return result

    def what_assumes(self, record_id: str) -> list[str]:
        """Return IDs of all records that record_id assumes (outgoing ``assumes`` edges)."""
        return [
            to_id
            for (from_id, to_id, et) in self._edges
            if from_id == record_id and et == "assumes"
        ]

    def successors(
        self,
        record_id: str,
        edge_types: frozenset[str] | None = None,
    ) -> list[str]:
        """Return direct successors of record_id across the given edge types."""
        types = edge_types if edge_types is not None else EDGE_TYPES
        return [
            to_id for (from_id, to_id, et) in self._edges if from_id == record_id and et in types
        ]

    def predecessors(
        self,
        record_id: str,
        edge_types: frozenset[str] | None = None,
    ) -> list[str]:
        """Return direct predecessors — records with edges pointing TO record_id."""
        types = edge_types if edge_types is not None else EDGE_TYPES
        return [
            from_id for (from_id, to_id, et) in self._edges if to_id == record_id and et in types
        ]

    def transitive_successors(
        self,
        record_id: str,
        edge_types: frozenset[str] | None = None,
    ) -> set[str]:
        """BFS from record_id across edge_types, returning all reachable IDs.

        Circular dependency safe — uses a visited set.
        """
        visited: set[str] = set()
        queue = [record_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self.successors(current, edge_types))
        visited.discard(record_id)
        return visited

    def transitive_predecessors(
        self,
        record_id: str,
        edge_types: frozenset[str] | None = None,
    ) -> set[str]:
        """BFS backwards from record_id, returning all upstream IDs."""
        visited: set[str] = set()
        queue = [record_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            queue.extend(self.predecessors(current, edge_types))
        visited.discard(record_id)
        return visited

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def edges(self) -> list[DependencyEdge]:
        """Return all current edges."""
        return list(self._edges.values())

    def edge_count(self) -> int:
        """Return the number of edges in the graph."""
        return len(self._edges)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist_edge(self, from_id: str, to_id: str, edge_type: str, *, active: bool) -> None:
        """Write/tombstone an edge record in the attached store."""
        from chronomemory.store import ChronoRecord

        assert self._store is not None
        edge_id = DependencyEdge.edge_id(from_id, to_id, edge_type)
        self._store.upsert(
            ChronoRecord(
                id=edge_id,
                kind="edge",
                status="active" if active else "tombstone",
                label=f"{from_id} --{edge_type}--> {to_id}",
                source_type="observed",
                confidence=1.0,
                data={"from_id": from_id, "to_id": to_id, "edge_type": edge_type},
            )
        )

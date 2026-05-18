# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Layer1Labs Silicon, Inc. / BitConcepts, LLC.
"""Epistemic rollback + propagation.

Phase 2 / Issue #2: Epistemic rollback + propagation
Spec: ESDB Master Spec §12

Spec invariants enforced:
  * Invariant 2: no silent disappearance — tombstone, not delete
  * Invariant 4: stale state may never override fresher canonical state
  * Invariant 5: contradictory canonical state may never coexist unresolved
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chronomemory.deps import DepGraph
    from chronomemory.store import ChronoStore

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

_CASCADE_EDGE_TYPES: frozenset[str] = frozenset(["depends_on", "derived_from"])


@dataclass
class RecordStatusChange:
    """Records a single status/confidence change during rollback propagation."""

    record_id: str
    previous_status: str
    new_status: str
    previous_confidence: float
    new_confidence: float


@dataclass
class RollbackReport:
    """Full report of an invalidation event and its cascaded effects.

    Written as a ``ChronoRecord(kind="rollback_event")`` to the WAL so
    the event is traceable in the audit chain.
    """

    target_id: str
    reason: str
    direct_change: RecordStatusChange | None = None
    cascaded: list[RecordStatusChange] = field(default_factory=list)

    @property
    def affected_ids(self) -> list[str]:
        """All record IDs touched by this rollback (direct + cascaded)."""
        ids: list[str] = []
        if self.direct_change:
            ids.append(self.direct_change.record_id)
        ids.extend(c.record_id for c in self.cascaded)
        return ids

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "reason": self.reason,
            "affected": self.affected_ids,
            "cascaded_count": len(self.cascaded),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def invalidate(
    record_id: str,
    reason: str,
    store: ChronoStore,
    dep_graph: DepGraph,
) -> RollbackReport:
    """Invalidate a record and cascade to all downstream dependents.

    Algorithm:
    1. Mark the target record ``status=invalidated`` via WAL upsert.
    2. BFS backward through ``depends_on`` / ``derived_from`` edges to find
       all records whose validity depends on the invalidated one.
    3. Cascade: downgrade each such record to ``status=hypothesis`` with
       halved confidence (minimum 0.0). Sets ``is_hypothesis=True``.
    4. Write a ``RollbackEvent`` WAL record summarising the full cascade.

    Circular dependency safe — BFS uses a visited set.

    Args:
        record_id: The record to invalidate.
        reason: Human-readable reason for the invalidation.
        store: The ChronoStore to read/write.
        dep_graph: The DepGraph to traverse for downstream records.

    Returns:
        A :class:`RollbackReport` describing everything that changed.
    """
    from chronomemory.store import ChronoRecord

    report = RollbackReport(target_id=record_id, reason=reason)

    # ── Step 1: invalidate the target ──────────────────────────────────
    existing = store.get(record_id)
    if existing is not None:
        prev_status = existing.status
        prev_conf = existing.confidence
        existing.status = "invalidated"
        store.upsert(existing)
        report.direct_change = RecordStatusChange(
            record_id=record_id,
            previous_status=prev_status,
            new_status="invalidated",
            previous_confidence=prev_conf,
            new_confidence=existing.confidence,
        )

    # ── Step 2: BFS backward through cascade edge types ────────────────
    visited: set[str] = {record_id}
    queue: list[str] = dep_graph.predecessors(record_id, _CASCADE_EDGE_TYPES)

    while queue:
        dep_id = queue.pop(0)
        if dep_id in visited:
            continue
        visited.add(dep_id)

        dep_rec = store.get(dep_id)
        if dep_rec is None:
            continue

        prev_status = dep_rec.status
        prev_conf = dep_rec.confidence

        # ── Step 3: cascade downgrade ───────────────────────────────────
        dep_rec.status = "hypothesis"
        dep_rec.confidence = max(0.0, dep_rec.confidence * 0.5)
        dep_rec.is_hypothesis = True
        store.upsert(dep_rec)

        report.cascaded.append(
            RecordStatusChange(
                record_id=dep_id,
                previous_status=prev_status,
                new_status="hypothesis",
                previous_confidence=prev_conf,
                new_confidence=dep_rec.confidence,
            )
        )

        # Continue BFS through the now-downgraded record's predecessors
        queue.extend(dep_graph.predecessors(dep_id, _CASCADE_EDGE_TYPES))

    # ── Step 4: write RollbackEvent WAL record ──────────────────────────
    store.upsert(
        ChronoRecord(
            id=f"ROLLBACK-{record_id}",
            kind="rollback_event",
            label=f"Invalidation of {record_id}: {reason}",
            source_type="observed",
            confidence=1.0,
            data=report.to_dict(),
        )
    )

    return report

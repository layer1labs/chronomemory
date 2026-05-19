# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Layer1Labs Silicon, Inc. / BitConcepts, LLC.
"""Extended query API — ESDB Master Spec §23 query functions.

Phase 2 / Issue #4: Complete query API (18 functions)

All functions accept a ``ChronoStore`` as their first argument and return
``list[ChronoRecord]`` or ``bool``.  Functions that require a dependency
graph degrade gracefully when ``dep_graph=None`` is passed.

The first six functions mirror the Rust reference implementation in
``crates/chronomemory/src/query.rs`` and are implemented first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chronomemory.deps import DepGraph
    from chronomemory.store import ChronoRecord, ChronoStore

# Infrastructure record kinds that must never appear in knowledge query results.
# These are system bookkeeping records, not agent-facing beliefs.
_INFRA_KINDS: frozenset[str] = frozenset(
    ["edge", "rollback_event", "token_metric", "skill_run"]
)

# ---------------------------------------------------------------------------
# §23 — Functions with Rust reference implementations (implement first)
# ---------------------------------------------------------------------------


def what_is_known(
    store: ChronoStore,
    kind: str | None = None,
) -> list[ChronoRecord]:
    """Return all active, high-confidence records (confidence ≥ 0.6).

    Infrastructure record kinds (edge, rollback_event, token_metric, skill_run)
    are excluded when no ``kind`` filter is specified, as they are system
    bookkeeping records rather than agent-facing beliefs.

    Mirrors Rust: ``what_is_known`` in query.rs.
    """
    results = store.query(kind=kind, rag_filter=True)
    if kind is None:
        return [r for r in results if r.kind not in _INFRA_KINDS]
    return results


def what_conflicts_with(
    store: ChronoStore,
    record_id: str,
    dep_graph: DepGraph | None = None,
) -> list[ChronoRecord]:
    """Return records that contradict the given record.

    Mirrors Rust: ``what_conflicts_with`` in query.rs.
    Degrades gracefully (returns []) when dep_graph is None.
    """
    if dep_graph is None:
        return []
    conflicting_ids = dep_graph.what_contradicts(record_id)
    return [r for r in (store.get(rid) for rid in conflicting_ids) if r is not None]


def what_depends_on(
    store: ChronoStore,
    record_id: str,
    dep_graph: DepGraph | None = None,
) -> list[ChronoRecord]:
    """Return all records that have a ``depends_on`` edge TO record_id.

    Mirrors Rust: ``what_depends_on`` in query.rs.
    """
    if dep_graph is None:
        return []
    dep_ids = dep_graph.predecessors(record_id, frozenset(["depends_on"]))
    return [r for r in (store.get(rid) for rid in dep_ids) if r is not None]


def what_changed_since(store: ChronoStore, seq: int) -> list[ChronoRecord]:
    """Return records written to the WAL after sequence number ``seq``.

    Mirrors Rust: ``what_changed_since`` in query.rs.
    """
    events = store.replay(from_seq=seq)
    seen_ids: dict[str, None] = {}  # preserve insertion order, deduplicate
    for event in events:
        if event.op in ("upsert", "migrate") and event.record_id:
            seen_ids[event.record_id] = None
    return [r for r in (store.get(rid) for rid in seen_ids) if r is not None]


def what_requires_reverification(store: ChronoStore) -> list[ChronoRecord]:
    """Return hypothesis records that need confirmation.

    Mirrors Rust: ``what_requires_reverification`` in query.rs.
    """
    return store.query(status="hypothesis")


def has_this_work_been_done(store: ChronoStore, action_label: str) -> bool:
    """Check whether equivalent completed work exists in the store.

    Mirrors Rust: ``has_this_work_been_done`` in query.rs.
    Case-insensitive substring match on label across decision/fact records.
    """
    label_lower = action_label.lower()
    for rec in store.query(status=""):
        if (
            rec.kind in ("decision", "fact")
            and rec.status == "active"
            and label_lower in rec.label.lower()
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# §23 — New query functions (12 of 18 missing from spec)
# ---------------------------------------------------------------------------


def why_do_we_believe(store: ChronoStore, claim_id: str) -> list[ChronoRecord]:
    """Return the evidence chain for a record.

    Returns the record itself plus any records whose IDs appear in its
    ``evidence`` list.
    """
    rec = store.get(claim_id)
    if rec is None:
        return []
    results: list[ChronoRecord] = [rec]
    for ev_ref in rec.evidence:
        ev_rec = store.get(ev_ref)
        if ev_rec is not None:
            results.append(ev_rec)
    return results


def what_context_packs_are_stale(store: ChronoStore) -> list[ChronoRecord]:
    """Return context_pack records that reference at least one invalidated record."""
    invalidated_ids = {r.id for r in store.query(status="invalidated")}
    stale: list[ChronoRecord] = []
    for rec in store.query(kind="context_pack"):
        entries = rec.data.get("entries", [])
        entry_ids = {e.get("record_id") for e in entries if isinstance(e, dict)}
        if entry_ids & invalidated_ids:
            stale.append(rec)
    return stale


def what_world_models_conflict(
    store: ChronoStore,
    dep_graph: DepGraph | None = None,
) -> list[ChronoRecord]:
    """Return ``world_state`` records with active contradictions.

    Degrades gracefully (returns []) when dep_graph is None.
    """
    if dep_graph is None:
        return []
    conflicting: list[ChronoRecord] = []
    for rec in store.query(kind="world_state"):
        if dep_graph.what_contradicts(rec.id):
            conflicting.append(rec)
    return conflicting


def what_assumptions_underlie(
    store: ChronoStore,
    plan_id: str,
    dep_graph: DepGraph | None = None,
) -> list[ChronoRecord]:
    """Return all records that plan_id transitively assumes.

    When dep_graph is None, returns just the plan record itself (if present).
    """
    if dep_graph is None:
        rec = store.get(plan_id)
        return [rec] if rec is not None else []
    assumed_ids = dep_graph.transitive_successors(plan_id, frozenset(["assumes"]))
    return [r for r in (store.get(rid) for rid in assumed_ids) if r is not None]


def what_generated_artifacts_depend_on(
    store: ChronoStore,
    fact_id: str,
    dep_graph: DepGraph | None = None,
) -> list[ChronoRecord]:
    """Return downstream ``artifact`` records that derive from fact_id.

    Edges are stored as ``artifact --generated_from/derived_from--> source``,
    so artifacts are the *predecessors* of fact_id via these edge types.

    Degrades gracefully (returns []) when dep_graph is None.
    """
    if dep_graph is None:
        return []
    # Artifacts point TO the source fact via generated_from/derived_from edges;
    # find all records that have such an edge pointing to fact_id.
    artifact_ids = dep_graph.transitive_predecessors(
        fact_id, frozenset(["generated_from", "derived_from"])
    )
    return [
        r
        for r in (store.get(rid) for rid in artifact_ids)
        if r is not None and r.kind == "artifact"
    ]


def what_confidence_collapsed(
    store: ChronoStore,
    threshold: float = 0.6,
) -> list[ChronoRecord]:
    """Return records whose confidence dropped below *threshold*.

    These are hypothesis records that started with higher confidence
    but were downgraded (e.g. by rollback cascade).
    """
    return [
        rec
        for rec in store.query(status="")
        if rec.confidence < threshold and rec.status == "hypothesis"
    ]


def what_can_agent_do_next(
    store: ChronoStore,
    goal_id: str,
    dep_graph: DepGraph | None = None,
) -> list[ChronoRecord]:
    """Return unblocked ``action`` records for a goal.

    An action is unblocked when all records it ``depends_on`` are active.
    When dep_graph is None, returns all active action records (no filtering).
    """
    actions = store.query(kind="action")
    if dep_graph is None:
        return actions
    unblocked: list[ChronoRecord] = []
    for action in actions:
        deps = dep_graph.successors(action.id, frozenset(["depends_on"]))
        if all((dep_rec := store.get(d)) is not None and dep_rec.status == "active" for d in deps):
            unblocked.append(action)
    return unblocked


def what_should_agent_not_do(store: ChronoStore) -> list[ChronoRecord]:
    """Return active ``stop_condition`` records — things the agent must not do."""
    return store.query(kind="stop_condition")


def what_skills_apply(store: ChronoStore, task_label: str) -> list[ChronoRecord]:
    """Return ``skill`` records whose activation keywords overlap with task_label."""
    label_words = set(task_label.lower().split())
    matching: list[ChronoRecord] = []
    for rec in store.query(kind="skill"):
        activation = rec.data.get("activation", [])
        if isinstance(activation, list):
            act_words = {str(w).lower() for w in activation}
            if label_words & act_words:
                matching.append(rec)
    return matching


def what_state_delta_would_complete(
    store: ChronoStore,
    goal_id: str,
    dep_graph: DepGraph | None = None,
) -> list[ChronoRecord]:
    """Return hypothesis records in the transitive chain of goal_id.

    These are the state changes still needed to complete the goal.
    When dep_graph is None, returns all hypothesis records in the store.
    """
    if dep_graph is None:
        return store.query(status="hypothesis")
    chain_ids = dep_graph.transitive_successors(goal_id)
    return [
        r
        for r in (store.get(rid) for rid in chain_ids)
        if r is not None and r.status == "hypothesis"
    ]


def is_this_action_duplicate(store: ChronoStore, action_label: str) -> bool:
    """Check for equivalent completed work — alias for has_this_work_been_done."""
    return has_this_work_been_done(store, action_label)


def what_context_pack_minimizes_tokens(
    store: ChronoStore,
    task_id: str,
    dep_graph: DepGraph | None = None,
) -> list[ChronoRecord]:
    """Return the optimal minimal set of records for task_id.

    Uses ContextPackCompiler with a conservative 2048-token budget to find
    the highest-confidence, most relevant records.
    """
    from chronomemory.context_pack import ContextPackCompiler

    compiler = ContextPackCompiler(store, dep_graph)
    pack = compiler.compile(task_id=task_id, goal=task_id, token_budget=2048)
    return [r for r in (store.get(e.record_id) for e in pack.entries) if r is not None]

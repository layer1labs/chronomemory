"""tests/test_query_ext.py — Extended query API tests (Issue #4, ≥2 per function)."""

from __future__ import annotations

from pathlib import Path

import pytest

from chronomemory import ChronoRecord, ChronoStore, DepGraph
from chronomemory import query as q

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> ChronoStore:
    s = ChronoStore(tmp_path).open()
    s.upsert(ChronoRecord(id="FACT-1", kind="fact", label="root fact", confidence=0.9))
    s.upsert(ChronoRecord(id="FACT-2", kind="fact", label="low conf fact", confidence=0.3))
    s.upsert(
        ChronoRecord(id="DEC-1", kind="decision", label="use ruff for linting", confidence=0.8)
    )
    s.upsert(
        ChronoRecord(
            id="HYP-1",
            kind="fact",
            label="hypothesis record",
            confidence=0.7,
            status="hypothesis",
            is_hypothesis=True,
        )
    )
    s.upsert(ChronoRecord(id="ACTION-1", kind="action", label="run lint", confidence=0.75))
    s.upsert(
        ChronoRecord(
            id="STOP-1", kind="stop_condition", label="do not delete prod", confidence=0.99
        )
    )
    s.upsert(
        ChronoRecord(
            id="SKILL-1",
            kind="skill",
            label="ruff linter skill",
            confidence=0.9,
            data={"activation": ["lint", "ruff", "python"]},
        )
    )
    s.upsert(
        ChronoRecord(
            id="FACT-INV", kind="fact", label="invalidated", confidence=0.9, status="invalidated"
        )
    )
    s.upsert(
        ChronoRecord(
            id="FACT-EV", kind="fact", label="evidence record", confidence=0.9, evidence=["FACT-1"]
        )
    )
    return s


@pytest.fixture()
def graph() -> DepGraph:
    g = DepGraph()
    g.add_edge("ACTION-1", "FACT-1", "depends_on")
    g.add_edge("FACT-1", "FACT-2", "assumes")
    g.add_edge("DEC-1", "FACT-INV", "contradicts")
    return g


# ---------------------------------------------------------------------------
# what_is_known
# ---------------------------------------------------------------------------


def test_what_is_known_returns_high_confidence(store: ChronoStore) -> None:
    result = q.what_is_known(store)
    ids = {r.id for r in result}
    assert "FACT-1" in ids
    assert "FACT-2" not in ids  # confidence 0.3 < 0.6


def test_what_is_known_filters_by_kind(store: ChronoStore) -> None:
    result = q.what_is_known(store, kind="decision")
    assert all(r.kind == "decision" for r in result)


# ---------------------------------------------------------------------------
# what_conflicts_with
# ---------------------------------------------------------------------------


def test_what_conflicts_with_returns_contradicting(store: ChronoStore, graph: DepGraph) -> None:
    result = q.what_conflicts_with(store, "DEC-1", graph)
    ids = {r.id for r in result}
    assert "FACT-INV" in ids


def test_what_conflicts_with_no_graph_returns_empty(store: ChronoStore) -> None:
    assert q.what_conflicts_with(store, "DEC-1") == []


# ---------------------------------------------------------------------------
# what_depends_on
# ---------------------------------------------------------------------------


def test_what_depends_on_returns_predecessors(store: ChronoStore, graph: DepGraph) -> None:
    result = q.what_depends_on(store, "FACT-1", graph)
    ids = {r.id for r in result}
    assert "ACTION-1" in ids


def test_what_depends_on_no_graph_returns_empty(store: ChronoStore) -> None:
    assert q.what_depends_on(store, "FACT-1") == []


# ---------------------------------------------------------------------------
# what_changed_since
# ---------------------------------------------------------------------------


def test_what_changed_since_seq_zero(store: ChronoStore) -> None:
    result = q.what_changed_since(store, 0)
    assert len(result) > 0


def test_what_changed_since_high_seq(store: ChronoStore) -> None:
    """High seq returns only recent records."""
    seq = store.wal_seq()
    result = q.what_changed_since(store, seq + 100)
    assert result == []


# ---------------------------------------------------------------------------
# what_requires_reverification
# ---------------------------------------------------------------------------


def test_what_requires_reverification_returns_hypotheses(store: ChronoStore) -> None:
    result = q.what_requires_reverification(store)
    ids = {r.id for r in result}
    assert "HYP-1" in ids


def test_what_requires_reverification_excludes_active(store: ChronoStore) -> None:
    result = q.what_requires_reverification(store)
    assert all(r.status == "hypothesis" for r in result)


# ---------------------------------------------------------------------------
# has_this_work_been_done
# ---------------------------------------------------------------------------


def test_has_this_work_been_done_true(store: ChronoStore) -> None:
    assert q.has_this_work_been_done(store, "ruff") is True


def test_has_this_work_been_done_false(store: ChronoStore) -> None:
    assert q.has_this_work_been_done(store, "does_not_exist_xyz") is False


# ---------------------------------------------------------------------------
# why_do_we_believe
# ---------------------------------------------------------------------------


def test_why_do_we_believe_returns_chain(store: ChronoStore) -> None:
    result = q.why_do_we_believe(store, "FACT-EV")
    ids = {r.id for r in result}
    assert "FACT-EV" in ids
    assert "FACT-1" in ids  # evidence link


def test_why_do_we_believe_missing_returns_empty(store: ChronoStore) -> None:
    assert q.why_do_we_believe(store, "DOES_NOT_EXIST") == []


# ---------------------------------------------------------------------------
# what_context_packs_are_stale
# ---------------------------------------------------------------------------


def test_what_context_packs_are_stale_finds_stale(tmp_path: Path) -> None:
    store = ChronoStore(tmp_path).open()
    store.upsert(
        ChronoRecord(id="INV-X", kind="fact", label="x", status="invalidated", confidence=0.9)
    )
    store.upsert(
        ChronoRecord(
            id="PACK-1",
            kind="context_pack",
            label="stale pack",
            confidence=0.9,
            data={"entries": [{"record_id": "INV-X"}]},
        )
    )
    result = q.what_context_packs_are_stale(store)
    assert any(r.id == "PACK-1" for r in result)


def test_what_context_packs_are_stale_clean_pack(tmp_path: Path) -> None:
    store = ChronoStore(tmp_path).open()
    store.upsert(ChronoRecord(id="ACTIVE-X", kind="fact", label="x", confidence=0.9))
    store.upsert(
        ChronoRecord(
            id="PACK-2",
            kind="context_pack",
            label="clean pack",
            confidence=0.9,
            data={"entries": [{"record_id": "ACTIVE-X"}]},
        )
    )
    result = q.what_context_packs_are_stale(store)
    assert not any(r.id == "PACK-2" for r in result)


# ---------------------------------------------------------------------------
# what_world_models_conflict
# ---------------------------------------------------------------------------


def test_what_world_models_conflict_finds_conflict(tmp_path: Path) -> None:
    store = ChronoStore(tmp_path).open()
    store.upsert(ChronoRecord(id="WM-1", kind="world_state", label="w1", confidence=0.9))
    store.upsert(ChronoRecord(id="WM-2", kind="world_state", label="w2", confidence=0.9))
    g = DepGraph()
    g.add_edge("WM-1", "WM-2", "contradicts")
    result = q.what_world_models_conflict(store, g)
    ids = {r.id for r in result}
    assert "WM-1" in ids


def test_what_world_models_conflict_no_graph(store: ChronoStore) -> None:
    assert q.what_world_models_conflict(store) == []


# ---------------------------------------------------------------------------
# what_assumptions_underlie
# ---------------------------------------------------------------------------


def test_what_assumptions_underlie_with_graph(store: ChronoStore, graph: DepGraph) -> None:
    result = q.what_assumptions_underlie(store, "FACT-1", graph)
    ids = {r.id for r in result}
    assert "FACT-2" in ids  # FACT-1 --assumes--> FACT-2


def test_what_assumptions_underlie_no_graph_returns_self(store: ChronoStore) -> None:
    result = q.what_assumptions_underlie(store, "FACT-1")
    assert any(r.id == "FACT-1" for r in result)


# ---------------------------------------------------------------------------
# what_generated_artifacts_depend_on
# ---------------------------------------------------------------------------


def test_what_generated_artifacts_depend_on(tmp_path: Path) -> None:
    store = ChronoStore(tmp_path).open()
    store.upsert(ChronoRecord(id="BASE", kind="fact", label="base", confidence=0.9))
    store.upsert(ChronoRecord(id="ART", kind="artifact", label="artifact", confidence=0.9))
    g = DepGraph()
    g.add_edge("ART", "BASE", "generated_from")
    result = q.what_generated_artifacts_depend_on(store, "BASE", g)
    assert any(r.id == "ART" for r in result)


def test_what_generated_artifacts_depend_on_no_graph(store: ChronoStore) -> None:
    assert q.what_generated_artifacts_depend_on(store, "FACT-1") == []


# ---------------------------------------------------------------------------
# what_confidence_collapsed
# ---------------------------------------------------------------------------


def test_what_confidence_collapsed_returns_low_hyp(store: ChronoStore) -> None:
    """HYP-1 has confidence 0.7 which is above 0.6; add a lower one."""
    store.upsert(
        ChronoRecord(id="HYP-LOW", kind="fact", label="low", confidence=0.2, status="hypothesis")
    )
    result = q.what_confidence_collapsed(store)
    ids = {r.id for r in result}
    assert "HYP-LOW" in ids


def test_what_confidence_collapsed_excludes_active(store: ChronoStore) -> None:
    result = q.what_confidence_collapsed(store)
    assert all(r.status == "hypothesis" for r in result)


# ---------------------------------------------------------------------------
# what_can_agent_do_next
# ---------------------------------------------------------------------------


def test_what_can_agent_do_next_unblocked(store: ChronoStore, graph: DepGraph) -> None:
    """ACTION-1 depends_on FACT-1 which is active → unblocked."""
    result = q.what_can_agent_do_next(store, "GOAL-1", graph)
    ids = {r.id for r in result}
    assert "ACTION-1" in ids


def test_what_can_agent_do_next_no_graph_returns_all(store: ChronoStore) -> None:
    result = q.what_can_agent_do_next(store, "GOAL-1")
    assert any(r.id == "ACTION-1" for r in result)


# ---------------------------------------------------------------------------
# what_should_agent_not_do
# ---------------------------------------------------------------------------


def test_what_should_agent_not_do_returns_stop_conditions(store: ChronoStore) -> None:
    result = q.what_should_agent_not_do(store)
    ids = {r.id for r in result}
    assert "STOP-1" in ids


def test_what_should_agent_not_do_empty_store(tmp_path: Path) -> None:
    store = ChronoStore(tmp_path).open()
    assert q.what_should_agent_not_do(store) == []


# ---------------------------------------------------------------------------
# what_skills_apply
# ---------------------------------------------------------------------------


def test_what_skills_apply_match(store: ChronoStore) -> None:
    result = q.what_skills_apply(store, "run lint check")
    ids = {r.id for r in result}
    assert "SKILL-1" in ids  # "lint" matches activation


def test_what_skills_apply_no_match(store: ChronoStore) -> None:
    result = q.what_skills_apply(store, "something completely different")
    assert result == []


# ---------------------------------------------------------------------------
# what_state_delta_would_complete
# ---------------------------------------------------------------------------


def test_what_state_delta_would_complete_with_graph(store: ChronoStore, graph: DepGraph) -> None:
    result = q.what_state_delta_would_complete(store, "FACT-1", graph)
    # No hypothesis records in FACT-1's chain with this graph
    assert isinstance(result, list)


def test_what_state_delta_would_complete_no_graph(store: ChronoStore) -> None:
    result = q.what_state_delta_would_complete(store, "ANY")
    assert all(r.status == "hypothesis" for r in result)


# ---------------------------------------------------------------------------
# is_this_action_duplicate
# ---------------------------------------------------------------------------


def test_is_this_action_duplicate_true(store: ChronoStore) -> None:
    assert q.is_this_action_duplicate(store, "ruff") is True


def test_is_this_action_duplicate_false(store: ChronoStore) -> None:
    assert q.is_this_action_duplicate(store, "xyz_never_done") is False


# ---------------------------------------------------------------------------
# what_context_pack_minimizes_tokens
# ---------------------------------------------------------------------------


def test_what_context_pack_minimizes_tokens_returns_list(store: ChronoStore) -> None:
    result = q.what_context_pack_minimizes_tokens(store, "FACT-1")
    assert isinstance(result, list)


def test_what_context_pack_minimizes_tokens_no_invalid(store: ChronoStore) -> None:
    result = q.what_context_pack_minimizes_tokens(store, "FACT-1")
    assert all(r.status not in ("tombstone", "invalidated") for r in result)

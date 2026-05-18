"""tests/test_context_pack.py — ContextPackCompiler unit tests (Issue #3, ≥6 tests)."""

from __future__ import annotations

from pathlib import Path

from chronomemory import ChronoRecord, ChronoStore, ContextPack, ContextPackCompiler


def _make_store(tmp_path: Path) -> ChronoStore:
    store = ChronoStore(tmp_path).open()
    store.upsert(ChronoRecord(id="F1", kind="fact", label="ruff lint python", confidence=0.95))
    store.upsert(ChronoRecord(id="F2", kind="fact", label="mypy typecheck python", confidence=0.85))
    store.upsert(ChronoRecord(id="F3", kind="fact", label="something unrelated", confidence=0.9))
    store.upsert(ChronoRecord(id="LOW", kind="fact", label="ruff check", confidence=0.3))
    store.upsert(
        ChronoRecord(
            id="TOMB", kind="fact", label="ruff tombstoned", confidence=0.95, status="tombstone"
        )
    )
    store.upsert(
        ChronoRecord(
            id="INV", kind="fact", label="ruff invalidated", confidence=0.95, status="invalidated"
        )
    )
    store.upsert(
        ChronoRecord(
            id="HYP", kind="fact", label="ruff hypothesis", confidence=0.95, status="hypothesis"
        )
    )
    return store


def test_compile_returns_context_pack(tmp_path: Path) -> None:
    """compile() returns a ContextPack instance."""
    store = _make_store(tmp_path)
    compiler = ContextPackCompiler(store)
    pack = compiler.compile(task_id="T1", goal="ruff lint")
    assert isinstance(pack, ContextPack)
    assert pack.task_id == "T1"
    assert pack.goal == "ruff lint"


def test_compile_includes_relevant_records(tmp_path: Path) -> None:
    """Records matching goal keywords and passing conf filter are included."""
    store = _make_store(tmp_path)
    compiler = ContextPackCompiler(store)
    pack = compiler.compile(task_id="T1", goal="ruff", token_budget=4096)
    included_ids = {e.record_id for e in pack.entries}
    assert "F1" in included_ids  # "ruff" in label


def test_compile_excludes_tombstoned(tmp_path: Path) -> None:
    """Tombstoned records are excluded and listed in pack.excluded."""
    store = _make_store(tmp_path)
    pack = ContextPackCompiler(store).compile("T1", "ruff")
    included_ids = {e.record_id for e in pack.entries}
    excluded_ids = {x.record_id for x in pack.excluded}
    assert "TOMB" not in included_ids
    assert "TOMB" in excluded_ids


def test_compile_excludes_invalidated(tmp_path: Path) -> None:
    """Invalidated records are excluded."""
    store = _make_store(tmp_path)
    pack = ContextPackCompiler(store).compile("T1", "ruff")
    included_ids = {e.record_id for e in pack.entries}
    assert "INV" not in included_ids


def test_compile_excludes_low_confidence(tmp_path: Path) -> None:
    """Records below the 0.6 confidence threshold are excluded."""
    store = _make_store(tmp_path)
    pack = ContextPackCompiler(store).compile("T1", "ruff")
    included_ids = {e.record_id for e in pack.entries}
    assert "LOW" not in included_ids


def test_compile_token_budget_enforced(tmp_path: Path) -> None:
    """token_count never exceeds token_budget."""
    store = _make_store(tmp_path)
    pack = ContextPackCompiler(store).compile("T1", "", token_budget=10)
    assert pack.token_count <= 10


def test_compile_sorted_by_confidence_desc(tmp_path: Path) -> None:
    """Entries are ordered highest-confidence first."""
    store = _make_store(tmp_path)
    pack = ContextPackCompiler(store).compile("T1", "", token_budget=99999)
    confs = [e.confidence for e in pack.entries]
    assert confs == sorted(confs, reverse=True)


def test_compile_to_dict_is_serializable(tmp_path: Path) -> None:
    """to_dict() returns a plain dict (JSON-injectable)."""
    import json

    store = _make_store(tmp_path)
    pack = ContextPackCompiler(store).compile("T1", "ruff")
    d = pack.to_dict()
    json_str = json.dumps(d)  # must not raise
    assert isinstance(json_str, str)
    assert d["task_id"] == "T1"
    assert "entries" in d
    assert "excluded" in d

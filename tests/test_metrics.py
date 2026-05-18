"""tests/test_metrics.py — Token metrics + skill system tests (Issue #5, ≥8 tests)."""

from __future__ import annotations

from pathlib import Path

from chronomemory import ChronoRecord, ChronoStore
from chronomemory.metrics import (
    find_skills,
    get_token_metrics,
    record_skill_run,
    record_token_metric,
    token_efficiency_report,
)

# ---------------------------------------------------------------------------
# Token metrics tests (§19)
# ---------------------------------------------------------------------------


def test_record_token_metric_writes_wal_record(tmp_path: Path) -> None:
    """record_token_metric writes a kind='token_metric' record to the WAL."""
    store = ChronoStore(tmp_path).open()
    record_token_metric(store, "TASK-1", 100, 200, 50, tool_calls=3, elapsed_ms=500)
    metrics = store.query(kind="token_metric")
    assert len(metrics) == 1
    m = metrics[0]
    assert m.data["task_id"] == "TASK-1"
    assert m.data["total_tokens"] == 350
    assert m.data["tool_calls"] == 3


def test_get_token_metrics_filters_by_task(tmp_path: Path) -> None:
    """get_token_metrics returns only records for the specified task."""
    store = ChronoStore(tmp_path).open()
    record_token_metric(store, "TASK-A", 100, 50, 25)
    record_token_metric(store, "TASK-B", 200, 100, 50)
    assert len(get_token_metrics(store, "TASK-A")) == 1
    assert len(get_token_metrics(store, "TASK-B")) == 1
    assert get_token_metrics(store, "TASK-A")[0].data["task_id"] == "TASK-A"


def test_token_efficiency_report_empty_store(tmp_path: Path) -> None:
    """token_efficiency_report returns zeros for empty store."""
    store = ChronoStore(tmp_path).open()
    report = token_efficiency_report(store)
    assert report["tokens_per_success"] == 0.0
    assert report["avg_tool_calls"] == 0.0
    assert report["duplicate_block_rate"] == 0.0


def test_token_efficiency_report_calculates_correctly(tmp_path: Path) -> None:
    """token_efficiency_report aggregates correctly."""
    store = ChronoStore(tmp_path).open()
    record_token_metric(
        store, "T1", 100, 100, 100, tool_calls=2, success=True, duplicates_blocked=1
    )
    record_token_metric(
        store, "T2", 200, 200, 200, tool_calls=4, success=False, duplicates_blocked=0
    )
    report = token_efficiency_report(store)
    # Only T1 is a success: total_tokens = 300
    assert report["tokens_per_success"] == 300.0
    # avg tool calls = (2 + 4) / 2 = 3.0
    assert report["avg_tool_calls"] == 3.0
    # duplicate_block_rate = 1 / 2 = 0.5
    assert report["duplicate_block_rate"] == 0.5


def test_record_token_metric_store_method(tmp_path: Path) -> None:
    """ChronoStore.record_token_metric() convenience method works."""
    store = ChronoStore(tmp_path).open()
    store.record_token_metric("TASK-CM", 50, 50, 50)
    metrics = store.get_token_metrics("TASK-CM")
    assert len(metrics) == 1


# ---------------------------------------------------------------------------
# Skill system tests (§21)
# ---------------------------------------------------------------------------


def test_find_skills_by_activation_keyword(tmp_path: Path) -> None:
    """find_skills matches skills by activation keyword intersection."""
    store = ChronoStore(tmp_path).open()
    store.upsert(
        ChronoRecord(
            id="SKILL-ruff",
            kind="skill",
            label="ruff linter",
            confidence=0.9,
            data={"activation": ["lint", "ruff", "python"]},
        )
    )
    result = find_skills(store, "run ruff linter")
    assert any(r.id == "SKILL-ruff" for r in result)


def test_find_skills_no_match(tmp_path: Path) -> None:
    """find_skills returns [] when no activation keywords match."""
    store = ChronoStore(tmp_path).open()
    store.upsert(
        ChronoRecord(
            id="SKILL-mypy",
            kind="skill",
            label="mypy",
            confidence=0.9,
            data={"activation": ["typecheck", "mypy"]},
        )
    )
    result = find_skills(store, "run ruff linter")
    assert result == []


def test_record_skill_run_writes_wal_record(tmp_path: Path) -> None:
    """record_skill_run writes a kind='skill_run' record to the WAL."""
    store = ChronoStore(tmp_path).open()
    record_skill_run(store, "SKILL-ruff", success=True, tokens_used=50, output={"errors": 0})
    runs = store.query(kind="skill_run")
    assert len(runs) == 1
    assert runs[0].data["skill_id"] == "SKILL-ruff"
    assert runs[0].data["success"] is True
    assert runs[0].confidence == 1.0


def test_record_skill_run_failure_lowers_confidence(tmp_path: Path) -> None:
    """Failed skill runs have confidence=0.5."""
    store = ChronoStore(tmp_path).open()
    record_skill_run(store, "SKILL-bad", success=False, tokens_used=100, output={"errors": 5})
    runs = store.query(kind="skill_run")
    assert runs[0].confidence == 0.5


def test_store_find_skills_method(tmp_path: Path) -> None:
    """ChronoStore.find_skills() convenience method works."""
    store = ChronoStore(tmp_path).open()
    store.upsert(
        ChronoRecord(
            id="SKILL-git",
            kind="skill",
            label="git commit",
            confidence=0.9,
            data={"activation": ["git", "commit", "push"]},
        )
    )
    result = store.find_skills("git push branch")
    assert any(r.id == "SKILL-git" for r in result)


def test_chain_valid_after_metrics(tmp_path: Path) -> None:
    """chain_valid() remains True after recording token metrics and skill runs."""
    store = ChronoStore(tmp_path).open()
    record_token_metric(store, "T-CHAIN", 10, 10, 10)
    record_skill_run(store, "SKILL-X", success=True, tokens_used=10, output={})
    assert store.chain_valid()

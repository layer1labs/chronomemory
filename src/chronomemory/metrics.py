# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Layer1Labs Silicon, Inc. / BitConcepts, LLC.
"""Token metrics tracking and skill system.

Phase 2 / Issue #5: Token metrics tracking and skill system
Spec: ESDB Master Spec §19 (Token Metrics) + §21 (Skill System)

Both systems write first-class ChronoRecord entries to the WAL so they
are covered by chain_valid() and survive replay automatically.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chronomemory.store import ChronoRecord, ChronoStore

# ---------------------------------------------------------------------------
# §19 — Token Metrics
# ---------------------------------------------------------------------------


def record_token_metric(
    store: ChronoStore,
    task_id: str,
    context_tokens: int,
    input_tokens: int,
    output_tokens: int,
    tool_calls: int = 0,
    elapsed_ms: int = 0,
    success: bool = True,
    duplicates_blocked: int = 0,
    claims_rejected: int = 0,
) -> None:
    """Write a TokenMetric WAL record for a completed agent task.

    Args:
        store: The ChronoStore to write to.
        task_id: Identifier for the task being measured.
        context_tokens: Tokens consumed by context injection.
        input_tokens: Tokens in the agent's input prompt.
        output_tokens: Tokens in the agent's output.
        tool_calls: Number of tool calls made during the task.
        elapsed_ms: Wall-clock duration in milliseconds.
        success: Whether the task completed successfully.
        duplicates_blocked: Number of duplicate work items blocked.
        claims_rejected: Number of hallucinated/invalid claims rejected.
    """
    from chronomemory.store import ChronoRecord

    metric_id = f"METRIC-{task_id}-{int(time.time() * 1000)}"
    store.upsert(
        ChronoRecord(
            id=metric_id,
            kind="token_metric",
            label=f"Token metric for task {task_id}",
            source_type="observed",
            confidence=1.0,
            data={
                "task_id": task_id,
                "context_tokens": context_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": context_tokens + input_tokens + output_tokens,
                "tool_calls": tool_calls,
                "elapsed_ms": elapsed_ms,
                "success": success,
                "duplicates_blocked": duplicates_blocked,
                "claims_rejected": claims_rejected,
            },
        )
    )


def get_token_metrics(store: ChronoStore, task_id: str) -> list[ChronoRecord]:
    """Return all TokenMetric records for a given task_id."""
    return [rec for rec in store.query(kind="token_metric") if rec.data.get("task_id") == task_id]


def token_efficiency_report(store: ChronoStore) -> dict[str, float]:
    """Compute aggregate token efficiency metrics across all tasks.

    Returns:
        dict with keys:
        - ``tokens_per_success``: average total tokens on successful tasks
        - ``avg_tool_calls``: average tool calls per task
        - ``duplicate_block_rate``: average duplicates blocked per task
    """
    all_metrics = store.query(kind="token_metric")
    if not all_metrics:
        return {
            "tokens_per_success": 0.0,
            "avg_tool_calls": 0.0,
            "duplicate_block_rate": 0.0,
        }

    successes = [m for m in all_metrics if m.data.get("success", False)]
    total_tokens_on_success = sum(m.data.get("total_tokens", 0) for m in successes)
    tokens_per_success = total_tokens_on_success / len(successes) if successes else 0.0

    total_tasks = len(all_metrics)
    avg_tool_calls = sum(m.data.get("tool_calls", 0) for m in all_metrics) / total_tasks
    total_duplicates = sum(m.data.get("duplicates_blocked", 0) for m in all_metrics)
    duplicate_block_rate = total_duplicates / total_tasks

    return {
        "tokens_per_success": tokens_per_success,
        "avg_tool_calls": avg_tool_calls,
        "duplicate_block_rate": duplicate_block_rate,
    }


# ---------------------------------------------------------------------------
# §21 — Skill System
# ---------------------------------------------------------------------------


def find_skills(store: ChronoStore, task_label: str) -> list[ChronoRecord]:
    """Return skill records whose activation keywords overlap with task_label.

    Activation keywords are stored in ``record.data["activation"]`` as a
    list of strings. Matching is case-insensitive word intersection.
    """
    label_words = set(task_label.lower().split())
    matching: list[ChronoRecord] = []
    for rec in store.query(kind="skill"):
        activation = rec.data.get("activation", [])
        if isinstance(activation, list):
            act_words = {str(w).lower() for w in activation}
            if label_words & act_words:
                matching.append(rec)
    return matching


def record_skill_run(
    store: ChronoStore,
    skill_id: str,
    success: bool,
    tokens_used: int,
    output: dict[str, Any],
) -> None:
    """Write a SkillRun WAL record capturing the result of one skill execution.

    Args:
        store: The ChronoStore to write to.
        skill_id: ID of the skill record (e.g. ``"SKILL-ruff-lint"``).
        success: Whether the skill execution succeeded.
        tokens_used: Total tokens consumed by this skill run.
        output: The skill's output data (must be JSON-serializable).
    """
    from chronomemory.store import ChronoRecord

    run_id = f"SKILLRUN-{skill_id}-{int(time.time() * 1000)}"
    store.upsert(
        ChronoRecord(
            id=run_id,
            kind="skill_run",
            label=f"Run of skill {skill_id}",
            source_type="observed",
            confidence=1.0 if success else 0.5,
            data={
                "skill_id": skill_id,
                "success": success,
                "tokens_used": tokens_used,
                "output": output,
            },
        )
    )

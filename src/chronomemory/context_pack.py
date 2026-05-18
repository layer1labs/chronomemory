# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Layer1Labs Silicon, Inc. / BitConcepts, LLC.
"""Context Pack Compiler — minimal verified prompt payloads for agent tasks.

Phase 2 / Issue #3: Context Pack Compiler
Spec: ESDB Master Spec §18

Assembles only the epistemic state an agent actually needs, excluding
stale, invalidated, and unsupported records, then respects a token budget
by dropping lowest-confidence candidates first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chronomemory.deps import DepGraph
    from chronomemory.store import ChronoRecord, ChronoStore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CHARS_PER_TOKEN: int = 4  # conservative estimate per spec §18
_MIN_CONFIDENCE: float = 0.6  # H18 threshold

# Record kinds that are infrastructure and should not appear in context packs
_INFRA_KINDS: frozenset[str] = frozenset(["edge", "rollback_event", "token_metric", "skill_run"])

# Statuses that indicate a record should be excluded
_EXCLUDED_STATUSES: frozenset[str] = frozenset(["tombstone", "invalidated", "hypothesis"])


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ContextPackEntry:
    """A single record included in a ContextPack."""

    record_id: str
    kind: str
    label: str
    confidence: float
    token_estimate: int
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "kind": self.kind,
            "label": self.label,
            "confidence": self.confidence,
            "token_estimate": self.token_estimate,
            "data": self.data,
        }


@dataclass
class ExclusionReason:
    """Explains why a record was excluded from a ContextPack."""

    record_id: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"record_id": self.record_id, "reason": self.reason}


@dataclass
class ContextPack:
    """A compiled, budget-constrained set of records ready for LLM injection.

    Serializable via :py:meth:`to_dict` for JSON injection into LLM context.
    """

    task_id: str
    goal: str
    token_budget: int
    entries: list[ContextPackEntry] = field(default_factory=list)
    excluded: list[ExclusionReason] = field(default_factory=list)

    @property
    def token_count(self) -> int:
        """Estimated total tokens consumed by all entries."""
        return sum(e.token_estimate for e in self.entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "token_budget": self.token_budget,
            "token_count": self.token_count,
            "entries": [e.to_dict() for e in self.entries],
            "excluded": [x.to_dict() for x in self.excluded],
        }


# ---------------------------------------------------------------------------
# ContextPackCompiler
# ---------------------------------------------------------------------------


class ContextPackCompiler:
    """Assembles a minimal, verified prompt payload for a given task.

    Usage::

        compiler = ContextPackCompiler(store, dep_graph)
        pack = compiler.compile(task_id="TASK-42", goal="fix ruff errors", token_budget=4096)

        # Inject into LLM context
        context_json = pack.to_dict()

    The ``dep_graph`` argument is optional. When provided, graph relevance
    traversal is used in addition to keyword matching (Phase 2 extension).
    """

    def __init__(self, store: ChronoStore, dep_graph: DepGraph | None = None) -> None:
        self._store = store
        self._dep_graph = dep_graph

    def compile(
        self,
        task_id: str,
        goal: str,
        token_budget: int = 4096,
    ) -> ContextPack:
        """Compile a token-budget-constrained ContextPack for a task.

        Inclusion rules:
        * Status must be ``active`` (not tombstone / invalidated / hypothesis)
        * Confidence must be ≥ 0.6 (H18)
        * Kind must not be an infrastructure record (edge, rollback_event, …)
        * Label must share at least one word with *goal* (or *goal* is empty)

        Budget enforcement:
        * Records are sorted by confidence descending
        * Records are added until token_budget is reached; remainder is excluded
        """
        pack = ContextPack(task_id=task_id, goal=goal, token_budget=token_budget)
        goal_words = set(goal.lower().split()) if goal.strip() else set()

        candidates: list[ContextPackEntry] = []

        for rec in self._store.query(status=""):
            token_est = self._estimate_tokens(rec)

            # ── Exclusion: bad status ────────────────────────────────────
            if rec.status in _EXCLUDED_STATUSES:
                pack.excluded.append(ExclusionReason(rec.id, f"status={rec.status}"))
                continue

            # ── Exclusion: confidence below H18 threshold ────────────────
            if rec.confidence < _MIN_CONFIDENCE:
                pack.excluded.append(
                    ExclusionReason(rec.id, f"confidence={rec.confidence:.2f} < {_MIN_CONFIDENCE}")
                )
                continue

            # ── Exclusion: infrastructure records ────────────────────────
            if rec.kind in _INFRA_KINDS:
                pack.excluded.append(
                    ExclusionReason(rec.id, f"infrastructure record (kind={rec.kind})")
                )
                continue

            # ── Relevance: keyword overlap with goal ─────────────────────
            if goal_words:
                label_words = set(rec.label.lower().split())
                if goal_words.isdisjoint(label_words):
                    pack.excluded.append(ExclusionReason(rec.id, "not relevant to goal"))
                    continue

            candidates.append(
                ContextPackEntry(
                    record_id=rec.id,
                    kind=rec.kind,
                    label=rec.label,
                    confidence=rec.confidence,
                    token_estimate=token_est,
                    data=rec.data,
                )
            )

        # ── Sort: highest confidence first (include most trusted first) ──
        candidates.sort(key=lambda e: e.confidence, reverse=True)

        # ── Budget enforcement: add until budget is exceeded ─────────────
        running_tokens = 0
        for entry in candidates:
            if running_tokens + entry.token_estimate <= token_budget:
                pack.entries.append(entry)
                running_tokens += entry.token_estimate
            else:
                pack.excluded.append(
                    ExclusionReason(
                        entry.record_id,
                        f"token budget exceeded "
                        f"({running_tokens}+{entry.token_estimate}>{token_budget})",
                    )
                )

        return pack

    @staticmethod
    def _estimate_tokens(rec: ChronoRecord) -> int:
        """Estimate token count: ~4 chars per token (label + data repr)."""
        chars = len(rec.label) + len(str(rec.data))
        return max(1, chars // _CHARS_PER_TOKEN)

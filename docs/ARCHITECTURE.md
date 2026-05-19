# Architecture — chronomemory

**Version:** 0.1.0 | **Phase:** Architecture | **Owner:** Layer1Labs Silicon, Inc. / BitConcepts, LLC.
**Spec ref:** ESDB-Specification.md v1.0 · CPSC-RAG-Specification.md r1.0

---

## Purpose

chronomemory is the **Epistemic State Database (ESDB)** — the shared persistence layer for all
Layer1Labs agentic AI projects. It stores *beliefs* produced by AI agents and human operators,
not mere data. Every record carries OEA (Ontological Epistemic Anchoring) fields that make
provenance, confidence, and generation depth first-class properties of every stored fact.

The library is intentionally minimal: zero runtime dependencies, pure Python stdlib,
single-writer WAL per project directory. It is the foundation that `specsmith`,
`chronoagent`, and `ctt-neural` share for cross-session epistemic state.

---

## Why beliefs, not facts

Traditional databases store facts. Agentic systems produce beliefs, and beliefs have
properties facts do not:

- **Provenance** — was this observed, inferred, or synthesized by an LLM?
- **Confidence** — how strongly is this belief held? (OEA rule H17)
- **Evidence** — what sources support it? (H20)
- **Recursion depth** — was this produced by an agent acting on agent output? (H16)
- **Model assumptions** — which model, at what temperature, produced this? (H21)

Without these properties, AI-generated content silently pollutes a project's knowledge base.
ESDB makes them mandatory on every record.

---

## Core design decisions

### 1. NDJSON is the canonical wire format

The WAL (`events.wal`) is Newline-Delimited JSON. Each line is a complete,
independently-parseable `WalEvent` JSON object (ESDB-Specification.md §2.4).

**Why not binary?** Cross-project readability requires format agreement. NDJSON is
human-inspectable, grep-able, diff-able, and requires no toolchain. The Rust crate in
`crates/chronomemory/` currently uses binary bincode — it must be migrated to NDJSON
before it can serve as the default implementation (Phase 2).

### 2. SHA-256 hash chain

Each WAL event stores:
- `prev_hash` — SHA-256 of the previous event's canonical JSON
- `hash` — SHA-256 of `{seq, ts, op, record_id, record, prev_hash, recursion_depth}`

The genesis event has `prev_hash = ""`. `chain_valid()` recomputes the full chain.
Any modification of a committed event makes every subsequent hash invalid.

### 3. Snapshot + tail replay

Every 50 events, the store writes `snapshot.json` — the full materialized state.
On `open()`, the store loads the snapshot and replays only the WAL tail
(`seq > snapshot.seq`). Startup is O(tail) not O(total WAL).
A corrupt snapshot is silently discarded; the store falls back to full WAL replay.

### 4. Zero external dependencies

The Python implementation uses only stdlib: `hashlib`, `json`, `os`, `shutil`,
`pathlib`, `dataclasses`. This is a hard invariant (REQ-CM-009).

### 5. Single-writer, multi-reader

Each project has exactly one `.chronomemory/` directory. Concurrent writes from the
same process are not supported (ESDB spec §12). Concurrent reads are supported:
each `ChronoStore` instance replays from disk independently.

---

## Module map

### `src/chronomemory/store.py`

The core implementation:
- `ChronoRecord` — universal record envelope with all 7 OEA fields
- `WalEvent` — single WAL log entry with `compute_hash()` and NDJSON serialisation
- `ChronoStore` — per-project WAL engine: `open/close`, `upsert`, `delete`, `query`,
  `get`, `compact`, `backup`, `replay`, `chain_valid`, `migrate_from_json`
- `open_store()` — convenience function

### `src/chronomemory/bridge.py`

Unified read/write adapter for projects with `.specsmith/*.json` legacy state.
Delegation:
1. `.chronomemory/events.wal` exists → delegate to `ChronoStore`
2. Otherwise → read flat `.specsmith/*.json` (read-only fallback)

Exposes: `EsdbBridge`, `EsdbRecord`, `EsdbStatus`.

### `src/chronomemory/deps.py` (Phase 2 — REQ-CM-015)

Typed dependency graph between ESDB records:
- `EDGE_TYPES` — frozenset of 9 valid edge types per spec §13: `assumes`, `contradicts`,
  `depends_on`, `derived_from`, `generated_from`, `invalidates`, `supports`,
  `supersedes`, `validated_by`
- `DependencyEdge` — frozen dataclass `(from_id, to_id, edge_type)`
- `DepGraph` — in-memory graph with optional WAL persistence via `ChronoStore`:
  - `add_edge / remove_edge` — persists as `ChronoRecord(kind="edge")` when store set
  - `what_depends_on / what_contradicts / what_assumes` — direct queries
  - `successors / predecessors` — filtered by edge type
  - `transitive_successors / transitive_predecessors` — BFS, circular-dep safe
  - `from_store(store)` — rebuilds from `kind="edge"` WAL records

Edges go through the normal `upsert()` path so `chain_valid()` covers them
automatically and they survive WAL replay without special handling.

### `src/chronomemory/rollback.py` (Phase 2 — REQ-CM-016)

Epistemic rollback and cascade propagation:
- `invalidate(record_id, reason, store, dep_graph) -> RollbackReport` — marks
  target `status=invalidated`, BFS-walks `depends_on`/`derived_from` predecessors,
  downgrades each to `status=hypothesis` with halved confidence, writes a
  `rollback_event` WAL record for full auditability
- `RollbackReport` — contains `direct_change`, `cascaded` list, `affected_ids`
- `ChronoStore.invalidate()` delegates here via lazy import

Satisfies ESDB invariants 2 (tombstone not delete), 4 (no stale override), 5
(no unresolved contradictions). Circular dependency safe via visited set.

### `src/chronomemory/context_pack.py` (Phase 2 — REQ-CM-017)

Token-budget-constrained context compilation for LLM injection:
- `ContextPackCompiler(store, dep_graph=None).compile(task_id, goal, token_budget=4096)`
- Exclusion rules (in order): `status` in `{tombstone, invalidated, hypothesis}`,
  `confidence < 0.6`, `kind` in infrastructure kinds, label shares no word with goal
- Budget enforcement: sort candidates by `confidence` descending, add until
  `token_budget` would be exceeded, exclude remainder
- Token estimate: `(len(label) + len(str(data))) // 4` chars-per-token (conservative)
- `ContextPack.to_dict()` — JSON-serializable for direct LLM context injection

### `src/chronomemory/query.py` (Phase 2 — REQ-CM-018)

18 query functions from ESDB spec §23. All accept `ChronoStore` as first arg;
functions requiring `DepGraph` degrade gracefully to a safe result when
`dep_graph=None`:

**Rust-mirrored (6):** `what_is_known`, `what_conflicts_with`, `what_depends_on`,
`what_changed_since`, `what_requires_reverification`, `has_this_work_been_done`

**New (12):** `why_do_we_believe`, `what_context_packs_are_stale`,
`what_world_models_conflict`, `what_assumptions_underlie`,
`what_generated_artifacts_depend_on`, `what_confidence_collapsed`,
`what_can_agent_do_next`, `what_should_agent_not_do`, `what_skills_apply`,
`what_state_delta_would_complete`, `is_this_action_duplicate`,
`what_context_pack_minimizes_tokens`

### `src/chronomemory/metrics.py` (Phase 2 — REQ-CM-019, REQ-CM-020)

Token metrics (spec §19) and skill system (spec §21):
- `record_token_metric(store, task_id, context_tokens, input_tokens, output_tokens,
  tool_calls, elapsed_ms, success, duplicates_blocked, claims_rejected)` — writes
  `kind=token_metric` WAL record
- `get_token_metrics(store, task_id)` — filters by task_id
- `token_efficiency_report(store)` — aggregates `{tokens_per_success, avg_tool_calls,
  duplicate_block_rate}` across all tasks
- `find_skills(store, task_label)` — keyword intersection on `data["activation"]`
- `record_skill_run(store, skill_id, success, tokens_used, output)` — writes
  `kind=skill_run`; `confidence=1.0` on success, `0.5` on failure

All functions write first-class WAL records so they survive replay and are
covered by `chain_valid()` without special handling.

### `crates/chronomemory/` (Rust core — Phase 3)

Advanced Rust implementation with dependency graphs, CPSC projection engine,
rollback cascade, context packs, token metrics. Currently uses binary bincode WAL.
Phase 3: migrate WAL to NDJSON, add PyO3 bindings, expose as optional accelerator.

---

## Data flow

```
Caller
  └─ ChronoStore.upsert(ChronoRecord)
       ├─ stamp recursion_depth from store context
       ├─ build WalEvent (seq, ts, prev_hash, compute_hash)
       ├─ atomic WAL append (tmp → fsync → rename)
       ├─ update in-memory state dict
       └─ if events_since_snapshot >= 50: write snapshot.json

Caller
  └─ ChronoStore.query(rag_filter=True)
       └─ filter in-memory state:
            confidence >= 0.6 AND status == "active"
```

---

## OEA field reference

| Field | OEA Rule | Default | Description |
|-------|----------|---------|-------------|
| `source_type` | H19 | `"observed"` | `observed` \| `inferred` \| `hypothesis` \| `synthetic` |
| `confidence` | H17 | `0.7` | Float 0.0–1.0 |
| `evidence` | H20 | `[]` | Source references |
| `epistemic_boundary` | H15 | `[]` | Scope constraints |
| `is_hypothesis` | H20 | `False` | Tentative belief flag |
| `model_assumptions` | H21 | `{}` | `{context_window, temperature, provider}` |
| `recursion_depth` | H16 | `0` | 0 = human; N = agent chain depth |

---

## Record kinds

`fact` · `hypothesis` · `requirement` · `testcase` · `decision` · `risk`

---

## Project layout

```
<project_root>/
  .chronomemory/
    events.wal        ← append-only NDJSON event log (canonical)
    snapshot.json     ← materialized state (written every 50 events)
    backup/           ← timestamped backup copies
```

---

## Consumer projects

| Project | Usage |
|---------|-------|
| `specsmith` | Governance store: requirements, test cases, session records |
| `chronoagent` | Memory write gate backing store; RAG retrieval via `rag_filter=True` |
| `ctt-neural` | Benchmark results (`kind=fact`); hypothesis lifecycle; CPSC audit trail |

---

## Out of scope

- Distributed / multi-writer consensus
- Encryption at rest (handled at filesystem level)
- Network transport or replication
- High-frequency per-step metrics (→ CSV / TensorBoard)
- Neural network checkpoint storage (→ PyTorch / numpy native formats)


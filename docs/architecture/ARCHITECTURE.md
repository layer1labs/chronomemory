# Architecture — chronomemory

**Version:** 0.1.0 | **Phase:** Inception | **Owner:** Layer1Labs Silicon, Inc. / BitConcepts, LLC.
**Spec ref:** ESDB-Specification.md v1.0 · CPSC-RAG-Specification.md r1.0

---

## Purpose

chronomemory is the **Epistemic State Database (ESDB)** — the shared persistence layer for all Layer1Labs agentic AI projects. It stores *beliefs* produced by AI agents and human operators, not mere data. Every record carries OEA (Ontological Epistemic Anchoring) fields that make provenance, confidence, and generation depth first-class properties of every stored fact.

The library is intentionally minimal: zero runtime dependencies, pure Python stdlib, single-writer WAL per project directory. It is the foundation that `specsmith`, `chronoagent`, and `ctt-neural` share for cross-session epistemic state.

---

## Why beliefs, not facts

Traditional databases store facts. Agentic systems produce beliefs, and beliefs have properties facts do not:

- **Provenance** — was this observed, inferred, or synthesized by an LLM?
- **Confidence** — how strongly is this belief held? (OEA rule H17)
- **Evidence** — what sources support it? (H20)
- **Recursion depth** — was this produced by an agent acting on agent output? (H16)
- **Model assumptions** — which model, at what temperature, produced this? (H21)

Without these properties, AI-generated content silently pollutes a project's knowledge base. ESDB makes them mandatory on every record.

---

## Core design decisions

### 1. NDJSON is the canonical wire format

The WAL (`events.wal`) is Newline-Delimited JSON. Each line is a complete, independently-parseable `WalEvent` JSON object. This is the canonical format per ESDB-Specification.md §2.4.

**Why not binary?** Cross-project readability requires format agreement. NDJSON is human-inspectable, grep-able, diff-able, and requires no toolchain to read. The Rust crate in `crates/chronomemory/` currently uses binary bincode — it must be migrated to NDJSON before it can serve as the default implementation (tracked as Phase 2 migration).

### 2. SHA-256 hash chain (Invariant: tamper-evident)

Each WAL event stores:
- `prev_hash` — SHA-256 of the previous event's canonical JSON
- `hash` — SHA-256 of `canonical_json({seq, ts, op, record_id, record, prev_hash, recursion_depth})`

The genesis event has `prev_hash = ""`. `chain_valid()` recomputes the full chain. Any modification of a committed event makes every subsequent hash invalid.

### 3. Snapshot + tail replay

Every 50 events, the store writes `snapshot.json` — the full materialized state at that point. On `open()`, the store loads the snapshot and replays only the WAL tail (events with `seq > snapshot.seq`). This keeps startup time O(tail) rather than O(total WAL).

A corrupt snapshot is silently discarded; the store falls back to full WAL replay.

### 4. Zero external dependencies

The Python implementation uses only stdlib: `hashlib`, `json`, `os`, `shutil`, `pathlib`, `dataclasses`. This is a hard invariant (REQ-CM-009). It means `pip install chronomemory` works in any Python environment with no transitive conflicts.

### 5. Single-writer, multi-reader

Each project has exactly one `.chronomemory/` directory. Concurrent writes from the same process are not supported (single-writer model per ESDB spec §12). Concurrent reads are supported: each `ChronoStore` instance replays from disk independently.

---

## Module map

### `src/chronomemory/store.py`
The core implementation. Contains:
- `ChronoRecord` — the universal record envelope with all 7 OEA fields
- `WalEvent` — a single WAL log entry with `compute_hash()` and NDJSON serialisation
- `ChronoStore` — per-project WAL engine with `open/close`, `upsert`, `delete`, `query`, `get`, `compact`, `backup`, `replay`, `chain_valid`, `migrate_from_json`
- `open_store()` — convenience function

### `src/chronomemory/bridge.py`
Unified read/write adapter for projects that may have `.specsmith/*.json` legacy state. Delegation strategy:
1. If `.chronomemory/events.wal` exists → delegate to `ChronoStore` (full WAL engine)
2. Otherwise → read flat `.specsmith/*.json` files (legacy read-only fallback)

Exposes: `EsdbBridge`, `EsdbRecord`, `EsdbStatus`.

### `crates/chronomemory/` (Rust core — Phase 2)
A more advanced Rust implementation with dependency graphs, CPSC projection engine, rollback with cascade, context packs, and token metrics. Currently uses binary bincode WAL format. **Must be migrated to NDJSON before production use as shared persistence** (tracked issue: WAL format unification).

Phase 2 plan: add PyO3 bindings to the Rust crate, switch WAL to NDJSON, expose as optional accelerator. `from chronomemory import ChronoStore` will transparently use Rust bindings when available.

---

## OEA field reference

| Field | OEA Rule | Description |
|-------|----------|-------------|
| `source_type` | H19 | `observed` \| `inferred` \| `hypothesis` \| `synthetic` |
| `confidence` | H17 | Float 0.0–1.0. Defaults to 0.7. |
| `evidence` | H20 | Source references supporting this record. |
| `epistemic_boundary` | H15 | Scope constraints (e.g. domain, time window). |
| `is_hypothesis` | H20 | True if this is a tentative belief. |
| `model_assumptions` | H21 | `{context_window, temperature, provider}` of generating model. |
| `recursion_depth` | H16 | 0 = human-initiated. N = produced by an agent chain of depth N. |

---

## Record kinds

`fact` · `hypothesis` · `requirement` · `testcase` · `decision` · `risk`

All kinds share the same `ChronoRecord` envelope. Kind is informational for query filtering.

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
| `specsmith` | Governance store: requirements, test cases, session records. CLI: `specsmith esdb *`. |
| `chronoagent` | Memory write gate backing store; RAG retrieval source via `memory_state`. |
| `ctt-neural` | Benchmark result store: `kind=fact, source_type=observed`; hypothesis tracking; CPSC projection audit trail. |

---

## Out of scope

- Distributed/multi-writer consensus (→ future `chronomemory-distributed`)
- Encryption at rest (handled at filesystem level)
- Network transport or replication
- High-frequency per-step metrics (→ CSV/TensorBoard; snapshot epoch summaries to ESDB)
- Neural network checkpoint storage (→ PyTorch/numpy native formats)

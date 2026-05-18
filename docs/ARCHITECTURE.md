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

### `crates/chronomemory/` (Rust core — Phase 2)

Advanced Rust implementation with dependency graphs, CPSC projection engine,
rollback cascade, context packs, token metrics. Currently uses binary bincode WAL.
Phase 2: migrate WAL to NDJSON, add PyO3 bindings, expose as optional accelerator.

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


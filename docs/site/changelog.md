# Changelog

## [Unreleased] — v0.1.0

Initial release. Extracted from `specsmith.esdb` and published as a standalone package.

### Added

**Python implementation** (`src/chronomemory/`)

- `ChronoStore` — per-project WAL-based ESDB with full lifecycle management
- `ChronoRecord` — universal record envelope with 7 mandatory OEA anti-hallucination fields
- `WalEvent` — NDJSON WAL event with SHA-256 hash chain
- `EsdbBridge` — unified read/write adapter with `.specsmith/` JSON fallback
- `EsdbRecord`, `EsdbStatus` — bridge type aliases
- `open_store()` — convenience factory function

**Core features**

- NDJSON write-ahead log (canonical wire format per ESDB-Specification.md §2.4)
- SHA-256 hash chain: `hash[N] = SHA256(hash[N-1] + canonical_json(payload[N]))`
- Snapshot + WAL tail replay: snapshot written every 50 events; startup loads snapshot + replays tail
- Atomic WAL writes: write-temp + fsync + rename
- Tombstone semantics: `delete()` never physically removes records
- Compact operation: truncates WAL to single sentinel event; chain remains valid
- Backup: timestamped copy of `.chronomemory/`
- Confidence-filtered RAG query (`rag_filter=True`): H18 enforcement
- Migration from `.specsmith/` JSON: idempotent, provenance-tagged

**Test suite** (113 tests, all passing)

- `tests/test_store.py` — snapshot replay, tombstone, migration, zero-deps (TEST-CM-004, 006, 008, 009)
- `tests/test_wal_chain.py` — hash chain, NDJSON format, atomic writes, cross-project compatibility (TEST-CM-001, 002, 007, 010)
- `tests/test_oea.py` — all 7 OEA fields, WAL round-trip, recursion depth (TEST-CM-003)
- `tests/test_query.py` — RAG filter, confidence thresholds (TEST-CM-005)
- `tests/test_robustness.py` — 60+ corruption, crash, boundary, lifecycle, concurrency tests
- `tests/test_bridge.py` — EsdbBridge delegation, JSON fallback, write operations

**Governance**

- specsmith governance scaffolding: `AGENTS.md`, `docs/requirements/chronomemory.yml` (REQ-CM-001..010), `docs/tests/chronomemory.yml` (TEST-CM-001..010)
- CI: 8-matrix test (Python 3.10–3.13 × Linux + Windows), lint, zero-deps job

**Rust core** (`crates/chronomemory/`)

- Rust crate with `Esdb`, `Store`, `WalWriter/WalReader`, `DepGraph`, `ProjectionEngine`, `Rollback`, `ContextPack`, `Metrics`
- 20 integration tests (TEST-ESDB-001..020)
- **Phase 2**: WAL format migration to NDJSON + PyO3 Python bindings (pending)

**Documentation** (`docs/site/`)

- ReadTheDocs setup with MkDocs Material theme
- Full navigation: installation, quickstart, concepts (OEA, WAL), API (ChronoStore, ChronoRecord, EsdbBridge), integrations (chronoagent, ctt-neural, specsmith), migration guide, Rust core roadmap

### Bug fixes

- `compact()` now resets `_last_hash = ""` before building the sentinel event, so `chain_valid()` returns `True` after compact + subsequent upserts
- `_replay_wal()` now guards against non-integer `seq` values (tampered WAL entries with string seq) — wrapped in nested `try/except` to skip malformed lines without aborting replay
- `EsdbRecord.kind` now has a default value (`"fact"`) matching `ChronoRecord`

### Breaking changes from specsmith vendored version

None. The WAL format is identical; imports change from `specsmith.esdb.*` to `chronomemory.*`.

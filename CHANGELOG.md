# Changelog

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] — 2026-05-20

### Added
- **Phase 3:** Optional Rust acceleration — `crates/chronomemory/` NDJSON WAL engine and
  `crates/chronomemory-py/` PyO3 Python bindings (`maturin develop` to enable) — closes #12 #13
- **Phase 4:** Rust–Python WAL cross-compatibility test suite (`tests/test_cross_compat.py`,
  5 tests — TEST-CM-025a–e) proving Python-written WAL passes Rust `verify_chain()` algorithm
- Rust integration test `TEST-ESDB-021` (`crates/chronomemory/tests/esdb_tests.rs`) verifying
  Rust WAL is readable as NDJSON with Python-compatible SHA-256 hash chain
- `docs/governance/DRIFT-METRICS.md` — governance drift metrics and equilibrium tracking
- 197 tests passing (up from 113), Python 3.10–3.13, Windows + Linux

### Fixed
- Security: PyO3 upgraded `0.22.6 → 0.24.2` (RUSTSEC-2025-0020)

### Changed
- specsmith governance phase promoted to `release` (SPECSMITH.yml v0.1.1)
- Version bumped to `0.1.1` in `pyproject.toml` and `docs/SPECSMITH.yml`

## [0.1.0] — 2026-05-18

### Added
- Initial Python implementation: `ChronoStore`, `ChronoRecord`, `WalEvent`, `EsdbBridge`
- NDJSON WAL with SHA-256 hash chain (canonical wire format per ESDB-Specification.md v1.0)
- 7 mandatory OEA anti-hallucination fields on every record (H15–H22):
  `source_type`, `confidence`, `evidence`, `epistemic_boundary`,
  `is_hypothesis`, `model_assumptions`, `recursion_depth`
- Snapshot + WAL tail replay on `open()` — O(tail) startup
- Confidence-filtered RAG query: `query(rag_filter=True)` applies H18 threshold (0.6)
- Tombstone semantics via `delete()` — no physical deletion, hash chain intact
- Atomic WAL writes: write-temp → fsync → `os.replace()` with fallback
- `migrate_from_json()` for importing `.specsmith/` legacy state (idempotent)
- `compact()` — WAL truncation to sentinel + fresh snapshot
- `backup()` — timestamped `.chronomemory/backup/` copies
- `EsdbBridge` — unified adapter with ChronoStore delegation and JSON fallback
- Zero runtime dependencies (pure Python stdlib: `hashlib`, `json`, `os`, `shutil`, `pathlib`)
- 113 tests, all passing on Python 3.10–3.13, Windows + Linux
- Rust core (`crates/chronomemory/`) — Phase 2, PyO3 bindings pending
- Full specsmith governance: ARCHITECTURE.md, REQUIREMENTS.md, TESTS.md,
  14 REQ-CM-* requirements, 16 TEST-CM-* test specs, 2 trace vault seals

### Fixed
- CI zero-deps check now correctly filters optional `; extra ==` entries
  from `Requires-Dist` metadata
- Ruff lint: resolved all 31 errors (I001, F401, F841, E741, E501) in test files

[0.1.1]: https://github.com/layer1labs/chronomemory/releases/tag/v0.1.1
[0.1.0]: https://github.com/layer1labs/chronomemory/releases/tag/v0.1.0

# Changelog

## [Unreleased]

### Added
- Initial Python implementation: ChronoStore, ChronoRecord, WalEvent, EsdbBridge
- NDJSON WAL with SHA-256 hash chain (canonical wire format per ESDB spec)
- OEA anti-hallucination fields on every record (H15–H22)
- Snapshot + WAL tail replay on open()
- Confidence-filtered RAG query (H18)
- Tombstone semantics — no physical deletion
- Atomic WAL writes (write-temp + fsync + rename)
- migrate_from_json() for .specsmith/ legacy state
- Zero runtime dependencies
- Test suite covering TEST-CM-001 through TEST-CM-010
- Rust core (crates/chronomemory/) — Phase 2 PyO3 bindings pending
- specsmith governance scaffolding (AGENTS.md, requirements.yml, tests.yml)

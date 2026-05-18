# Test Specification — chronomemory

**Namespace:** TEST-CM | **Spec ref:** ESDB-Specification.md v1.0
**Coverage:** 113 tests, Python 3.10–3.13, Windows + Linux

---

## Test files

| File | Description |
|------|-------------|
| `tests/test_store.py` | Snapshot replay, tombstone, migration, zero-deps |
| `tests/test_wal_chain.py` | Hash chain integrity, NDJSON format, atomic write |
| `tests/test_oea.py` | OEA field round-trips, recursion depth stamping |
| `tests/test_query.py` | Confidence filtering, RAG threshold, kind/status filters |
| `tests/test_robustness.py` | Corruption, crash-sim, boundary, lifecycle |
| `tests/test_bridge.py` | EsdbBridge delegation, JSON fallback, write ops |

---

## Traceability matrix

### TEST-CM-001 — WAL hash chain integrity
- **Covers:** REQ-CM-002
- **File:** `tests/test_wal_chain.py::test_wal_hash_chain_integrity`
- **Status:** passing

### TEST-CM-002 — WAL is NDJSON
- **Covers:** REQ-CM-003
- **File:** `tests/test_wal_chain.py::test_wal_is_ndjson`
- **Status:** passing

### TEST-CM-003 — Chain detects tampering
- **Covers:** REQ-CM-002
- **File:** `tests/test_wal_chain.py::test_chain_detects_wal_tampering`
- **Status:** passing

### TEST-CM-004 — Snapshot + WAL tail replay
- **Covers:** REQ-CM-004
- **File:** `tests/test_store.py::test_snapshot_replay_consistency`
- **Status:** passing

### TEST-CM-005 — RAG filter confidence threshold
- **Covers:** REQ-CM-005
- **File:** `tests/test_query.py::test_rag_filter_confidence_threshold`
- **Status:** passing

### TEST-CM-006 — Tombstone no physical removal
- **Covers:** REQ-CM-001, REQ-CM-006
- **File:** `tests/test_store.py::test_tombstone_no_physical_removal`
- **Status:** passing

### TEST-CM-007 — Atomic WAL write fallback
- **Covers:** REQ-CM-007
- **File:** `tests/test_wal_chain.py::test_atomic_wal_write_fallback_on_replace_failure`
- **Status:** passing

### TEST-CM-008 — migrate_from_json idempotent
- **Covers:** REQ-CM-008
- **File:** `tests/test_store.py::test_migrate_from_json_idempotent`
- **Status:** passing

### TEST-CM-009 — Zero external dependencies
- **Covers:** REQ-CM-009
- **File:** `tests/test_store.py::test_zero_external_deps`
- **Status:** passing

### TEST-CM-010 — OEA fields present with defaults
- **Covers:** REQ-CM-010
- **File:** `tests/test_oea.py` — full suite
- **Status:** passing

### TEST-CM-011 — Cross-platform WAL compatibility
- **Covers:** REQ-CM-011
- **File:** `tests/test_wal_chain.py::test_cross_project_wal_compatibility`
- **Status:** passing

### TEST-CM-012 — Graceful corruption recovery
- **Covers:** REQ-CM-012
- **File:** `tests/test_robustness.py::TestWalCorruption`, `TestSnapshotCorruption`
- **Status:** passing

### TEST-CM-013 — Startup time boundary
- **Covers:** REQ-CM-013
- **File:** `tests/test_robustness.py::test_exactly_51_records_snapshot_plus_tail`
- **Status:** passing

### TEST-CM-014 — EsdbBridge delegation and fallback
- **Covers:** REQ-CM-014
- **File:** `tests/test_bridge.py` — full suite
- **Status:** passing

### TEST-CM-015 — Write failure / crash simulation
- **Covers:** REQ-CM-007
- **File:** `tests/test_robustness.py::TestWriteFailureSimulation`
- **Status:** passing

### TEST-CM-016 — Recursion depth stamping
- **Covers:** REQ-CM-010
- **File:** `tests/test_oea.py::test_recursion_depth_stamped_by_store`
- **Status:** passing

---

## Requirements coverage summary

| Requirement | Covered by | Status |
|-------------|-----------|--------|
| REQ-CM-001 | TEST-CM-006 | ✓ |
| REQ-CM-002 | TEST-CM-001, TEST-CM-003 | ✓ |
| REQ-CM-003 | TEST-CM-002 | ✓ |
| REQ-CM-004 | TEST-CM-004 | ✓ |
| REQ-CM-005 | TEST-CM-005 | ✓ |
| REQ-CM-006 | TEST-CM-006 | ✓ |
| REQ-CM-007 | TEST-CM-007, TEST-CM-015 | ✓ |
| REQ-CM-008 | TEST-CM-008 | ✓ |
| REQ-CM-009 | TEST-CM-009 | ✓ |
| REQ-CM-010 | TEST-CM-010, TEST-CM-016 | ✓ |
| REQ-CM-011 | TEST-CM-011 | ✓ |
| REQ-CM-012 | TEST-CM-012 | ✓ |
| REQ-CM-013 | TEST-CM-013 | ✓ |
| REQ-CM-014 | TEST-CM-014 | ✓ |

**Coverage: 14/14 requirements = 100%**

---

*Run: `pytest tests/ -v --tb=short` — 113 tests, all passing.*

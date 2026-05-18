# Requirements — chronomemory

**Namespace:** REQ-CM | **Spec ref:** ESDB-Specification.md v1.0
**Canonical YAML:** `docs/requirements/chronomemory.yml`

---

## REQ-CM-001. WAL Append-Only with Tombstone Semantics
- **ID:** REQ-CM-001
- **Title:** WAL Append-Only with Tombstone Semantics
- **Description:** The WAL (events.wal) must be append-only. Physical deletion is prohibited. Logical removal writes a delete event setting status=tombstone. chain_valid() must return False if any link is broken.
- **Status:** implemented
- **Platform:** all (Windows, Linux, macOS) | Python 3.10-3.13
- **Boundary:** Single-writer process; WAL at <project>/.chronomemory/events.wal
- **Source:** ESDB-Specification.md s2.4
- **Test_Ids:** ['TEST-CM-001', 'TEST-CM-006']

## REQ-CM-002. SHA-256 Hash Chain Integrity
- **ID:** REQ-CM-002
- **Title:** SHA-256 Hash Chain Integrity
- **Description:** Every WAL event must carry prev_hash and hash (SHA-256 of the event payload with sort_keys=True). chain_valid() must return False if any link is broken.
- **Status:** implemented
- **Platform:** all
- **Boundary:** Per-project WAL; one chain per store instance
- **Source:** ESDB-Specification.md s2.4
- **Test_Ids:** ['TEST-CM-001', 'TEST-CM-003']

## REQ-CM-003. NDJSON Canonical WAL Format
- **ID:** REQ-CM-003
- **Title:** NDJSON Canonical WAL Format
- **Description:** The WAL must be Newline-Delimited JSON. Every non-empty line must be independently parseable as JSON. Binary formats are prohibited.
- **Status:** implemented
- **Platform:** all
- **Boundary:** events.wal; binary formats (bincode) are Phase 2 only
- **Source:** ESDB-Specification.md s2.4
- **Test_Ids:** ['TEST-CM-002']

## REQ-CM-004. Snapshot and WAL Tail Replay on Open
- **ID:** REQ-CM-004
- **Title:** Snapshot and WAL Tail Replay on Open
- **Description:** ChronoStore writes snapshot.json every 50 events. On open(), load snapshot and replay only events with seq > snapshot.seq. Corrupt snapshot must be discarded silently.
- **Status:** implemented
- **Platform:** all
- **Boundary:** <project>/.chronomemory/snapshot.json; trigger at 50 events
- **Source:** ESDB-Specification.md s2.4
- **Test_Ids:** ['TEST-CM-004', 'TEST-CM-013']

## REQ-CM-005. Confidence-Filtered RAG Query (H18)
- **ID:** REQ-CM-005
- **Title:** Confidence-Filtered RAG Query (H18)
- **Description:** query(rag_filter=True) must return only records with confidence >= 0.6 AND status == active. Implements OEA rule H18.
- **Status:** implemented
- **Platform:** all
- **Boundary:** In-memory state; default threshold 0.6
- **Source:** ESDB-Specification.md s3 s6
- **Test_Ids:** ['TEST-CM-005']

## REQ-CM-006. Tombstone Semantics - No Physical Deletion
- **ID:** REQ-CM-006
- **Title:** Tombstone Semantics - No Physical Deletion
- **Description:** delete(record_id) must write a delete WAL event and set status=tombstone in memory. Physical removal from disk is not permitted. Satisfies ESDB Invariant 2.
- **Status:** implemented
- **Platform:** all
- **Boundary:** WAL and in-memory state; no physical removal ever
- **Source:** ESDB-Specification.md s2.3
- **Test_Ids:** ['TEST-CM-006']

## REQ-CM-007. Atomic WAL Writes
- **ID:** REQ-CM-007
- **Title:** Atomic WAL Writes
- **Description:** WAL appends must be atomic: write to .wal.tmp, fsync, then os.replace(). If os.replace() fails, fall back to direct append without raising.
- **Status:** implemented
- **Platform:** all
- **Boundary:** Write path; .wal.tmp temp file in .chronomemory/
- **Source:** ESDB-Specification.md s2.4
- **Test_Ids:** ['TEST-CM-007', 'TEST-CM-012']

## REQ-CM-008. Idempotent JSON Migration
- **ID:** REQ-CM-008
- **Title:** Idempotent JSON Migration
- **Description:** migrate_from_json(specsmith_dir) must import .specsmith/*.json using upsert semantics. Records with unchanged id+label+status must be skipped. Governance status maps to ESDB status.
- **Status:** implemented
- **Platform:** all
- **Boundary:** .specsmith/requirements.json and .specsmith/testcases.json
- **Source:** ESDB-Specification.md s5.3
- **Test_Ids:** ['TEST-CM-008']

## REQ-CM-009. Zero Runtime Dependencies
- **ID:** REQ-CM-009
- **Title:** Zero Runtime Dependencies
- **Description:** The package must declare dependencies=[] in pyproject.toml and import successfully with python -S. Only stdlib modules are permitted.
- **Status:** implemented
- **Platform:** all
- **Boundary:** pyproject.toml [project.dependencies] must be empty
- **Source:** ESDB-Specification.md s11
- **Test_Ids:** ['TEST-CM-009']

## REQ-CM-010. OEA Field Completeness
- **ID:** REQ-CM-010
- **Title:** OEA Field Completeness
- **Description:** Every ChronoRecord must carry all 7 OEA fields with safe defaults. recursion_depth must be stamped by the store at upsert time.
- **Status:** implemented
- **Platform:** all
- **Boundary:** Every ChronoRecord written to WAL
- **Source:** ESDB-Specification.md s3
- **Test_Ids:** ['TEST-CM-003']

## REQ-CM-011. Cross-Platform Compatibility
- **ID:** REQ-CM-011
- **Title:** Cross-Platform Compatibility
- **Description:** ChronoStore must function identically on Windows, Linux, macOS on Python 3.10-3.13. CRLF line endings must be handled correctly.
- **Status:** implemented
- **Platform:** Windows, Linux, macOS | Python 3.10-3.13
- **Boundary:** WAL file I/O; CRLF vs LF line endings; filesystem path separators
- **Source:** ESDB-Specification.md s11
- **Test_Ids:** ['TEST-CM-011']

## REQ-CM-012. Graceful Corruption Recovery
- **ID:** REQ-CM-012
- **Title:** Graceful Corruption Recovery
- **Description:** ChronoStore must recover without raising from: truncated lines, garbage JSON, missing hash fields, wrong types, binary bytes, empty WAL, whitespace-only WAL, corrupt snapshot.
- **Status:** implemented
- **Platform:** all
- **Boundary:** WAL replay and snapshot load paths
- **Source:** ESDB-Specification.md s2.4
- **Test_Ids:** ['TEST-CM-012']

## REQ-CM-013. Startup Performance - Snapshot Plus Tail Replay
- **ID:** REQ-CM-013
- **Title:** Startup Performance - Snapshot Plus Tail Replay
- **Description:** On a store with 10000+ events and a valid snapshot, open() must complete in under 500ms. O(tail) not O(total WAL) startup.
- **Status:** defined
- **Platform:** all
- **Boundary:** open() on a store with 10000+ events + valid snapshot
- **Source:** ESDB-Specification.md s2.4
- **Test_Ids:** ['TEST-CM-013']

## REQ-CM-014. EsdbBridge Delegation and JSON Fallback
- **ID:** REQ-CM-014
- **Title:** EsdbBridge Delegation and JSON Fallback
- **Description:** EsdbBridge must delegate to ChronoStore when events.wal exists. Falls back to .specsmith/*.json when no WAL. Write ops return False without WAL.
- **Status:** implemented
- **Platform:** all
- **Boundary:** Reads .chronomemory/events.wal; falls back to .specsmith/*.json
- **Source:** ESDB-Specification.md s5.3
- **Test_Ids:** ['TEST-CM-014']

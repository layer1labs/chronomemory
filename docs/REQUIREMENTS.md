# Requirements — chronomemory

**Namespace:** REQ-CM | **Spec ref:** ESDB-Specification.md v1.0
**Owner:** Layer1Labs Silicon, Inc. / BitConcepts, LLC.
**Canonical YAML:** `docs/requirements/chronomemory.yml`

---

## Status legend

| Status | Meaning |
|--------|---------|
| `accepted` | Implemented and verified |
| `defined` | Stated, scoped, not yet verified |
| `draft` | Under discussion |

---

## Functional requirements

### REQ-CM-001 — WAL append-only semantics
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all (Windows, Linux, macOS) | **Python:** 3.10–3.13
**Boundary:** Single-writer process; WAL at `<project>/.chronomemory/events.wal`
**Verified by:** TEST-CM-001, TEST-CM-006

The WAL (`events.wal`) MUST be append-only. Physical deletion of records is
prohibited. Logical removal is performed by writing a `delete` event that sets
`status = "tombstone"` on the target record. Every event carries the SHA-256
of the previous event's canonical JSON payload, forming a tamper-evident chain.
`chain_valid()` MUST return `False` if any link is broken.

---

### REQ-CM-002 — SHA-256 hash chain integrity
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** Per-project WAL; one chain per store instance
**Verified by:** TEST-CM-001, TEST-CM-003

Every WAL event MUST carry:
- `prev_hash`: SHA-256 of the previous event's canonical JSON (empty string for genesis)
- `hash`: SHA-256 of `{seq, ts, op, record_id, record, prev_hash, recursion_depth}`
  serialised with `sort_keys=True, ensure_ascii=False`

`chain_valid()` MUST return `False` if any event's stored hash does not match its
recomputed hash, or if any `prev_hash` does not match the preceding event's `hash`.

---

### REQ-CM-003 — NDJSON canonical WAL format
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** `events.wal`; binary formats (bincode) are Phase 2 only
**Verified by:** TEST-CM-002

The WAL file MUST be Newline-Delimited JSON (NDJSON). Every non-empty line MUST be
a valid, independently-parseable JSON object. Binary formats are prohibited for the
canonical WAL. NDJSON must be human-inspectable without special tooling.

---

### REQ-CM-004 — Snapshot + WAL tail replay
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** `<project>/.chronomemory/snapshot.json`; trigger at 50 events
**Verified by:** TEST-CM-004, TEST-CM-013

The store MUST write `snapshot.json` (full materialised state) every 50 appended
events. On `open()`, the store MUST load the snapshot and replay only events with
`seq > snapshot.seq`. A corrupt or missing snapshot MUST be silently discarded;
the store MUST fall back to full WAL replay without raising an exception.

---

### REQ-CM-005 — Confidence-filtered RAG query (H18)
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** In-memory state; default threshold 0.6
**Verified by:** TEST-CM-005

`query(rag_filter=True)` MUST return only records where:
- `confidence >= 0.6` (H18 RAG threshold), AND
- `status == "active"`

`query(min_confidence=X)` MUST apply `max(X, rag_filter_threshold)` so a custom
threshold never silently reduces below 0.6 when `rag_filter=True`.

---

### REQ-CM-006 — Tombstone semantics
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** WAL and in-memory state; no physical removal ever
**Verified by:** TEST-CM-006

`delete(record_id)` MUST write a `delete` WAL event and set `status = "tombstone"`
in memory. The record MUST remain retrievable via `get()` and MUST be excluded from
`query(status="active")`. Physical removal from disk is not permitted. Tombstones
are required by ESDB Invariant 2 (no silent disappearance).

---

### REQ-CM-007 — Atomic WAL write
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** Write path; `.wal.tmp` temp file in `.chronomemory/`
**Verified by:** TEST-CM-007, TEST-CM-012

WAL appends MUST be atomic: write to a `.wal.tmp` temp file, `fsync`, then
`os.replace()` to rename over the live WAL. A crash between temp-write and rename
MUST leave the prior WAL intact. If `os.replace()` fails, the store MUST fall back
to direct append without raising an exception.

---

### REQ-CM-008 — Idempotent JSON migration
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** `.specsmith/requirements.json` and `.specsmith/testcases.json`
**Verified by:** TEST-CM-008

`migrate_from_json(specsmith_dir)` MUST import requirements and test cases from
`.specsmith/*.json` using upsert semantics (idempotent by ID + label). Records with
unchanged label and status MUST be skipped (counted as `skipped`). Governance
`status` values (`defined`, `implemented`, etc.) MUST be mapped to ESDB `status`
(`active` / `deprecated`) — they are different concepts.

---

### REQ-CM-009 — Zero runtime dependencies
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** `pyproject.toml [project.dependencies]` must be empty
**Verified by:** TEST-CM-009

The Python package MUST declare `dependencies = []` in `pyproject.toml`. The
package MUST import successfully in a `python -S` subprocess (no site-packages).
The only permitted imports are Python standard library modules: `hashlib`, `json`,
`os`, `shutil`, `pathlib`, `dataclasses`, `typing`.

---

### REQ-CM-010 — OEA field completeness
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** Every `ChronoRecord` written to WAL
**Verified by:** TEST-CM-003

Every `ChronoRecord` MUST carry all 7 OEA fields with safe defaults:
`source_type="observed"`, `confidence=0.7`, `evidence=[]`,
`epistemic_boundary=[]`, `is_hypothesis=False`, `model_assumptions={}`,
`recursion_depth=0`.

`recursion_depth` MUST be stamped by the store at upsert time using the
`ChronoStore(recursion_depth=N)` context, not by the caller.

---

### REQ-CM-011 — Cross-platform compatibility
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** Windows, Linux, macOS | **Python:** 3.10–3.13
**Boundary:** WAL file I/O; CRLF vs LF line endings; filesystem path separators
**Verified by:** TEST-CM-011

The library MUST function identically on Windows, Linux, and macOS, on Python
3.10, 3.11, 3.12, and 3.13. WAL files written on one platform MUST be readable
on any other platform. CRLF line endings MUST be handled correctly on all platforms.

---

### REQ-CM-012 — Graceful corruption recovery
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** WAL replay and snapshot load paths
**Verified by:** TEST-CM-012

The store MUST recover gracefully from the following WAL/snapshot conditions without
raising an exception: truncated last WAL line, garbage non-JSON lines, missing hash
fields, wrong field types (e.g. `seq` as string), binary bytes at WAL start, CRLF
line endings, empty WAL, whitespace-only WAL, corrupt snapshot JSON,
invalid records inside snapshot.

---

## Non-functional requirements

### REQ-CM-013 — Startup time
**Status:** defined | **Priority:** P2 | **OEA source_type:** inferred
**Platform:** all | **Boundary:** `open()` on a store with ≥10,000 events + valid snapshot
**Verified by:** TEST-CM-013

On a WAL with 10,000+ events and a valid snapshot, `open()` MUST complete in
under 500 ms on standard developer hardware (2GHz+ CPU, SSD). The
snapshot + tail-replay architecture ensures O(tail) startup.

---

### REQ-CM-014 — EsdbBridge fallback
**Status:** accepted | **Priority:** P1 | **OEA source_type:** observed
**Platform:** all | **Boundary:** Reads `.chronomemory/events.wal`; falls back to `.specsmith/*.json`
**Verified by:** TEST-CM-014

`EsdbBridge` MUST delegate to `ChronoStore` when `.chronomemory/events.wal`
exists. When no WAL exists, it MUST fall back to reading `.specsmith/*.json`
(legacy read-only). Write operations (`upsert_record`, `delete_record`) MUST
return `False` when no WAL is available.

---

*Canonical YAML source: `docs/requirements/chronomemory.yml` — 14 requirements.*
*Regenerate: `specsmith export --output docs/REQUIREMENTS.md`*

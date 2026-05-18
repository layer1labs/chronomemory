# Migration Guide

## Migrating from specsmith.esdb to chronomemory

specsmith ≥ 0.11.3 contains a vendored ESDB implementation at `specsmith.esdb.*`. The standalone `chronomemory` package is the canonical version going forward.

### 1. Install chronomemory

```bash
pip install git+https://github.com/layer1labs/chronomemory.git
```

### 2. Update imports

| Old import | New import |
|------------|------------|
| `from specsmith.esdb.store import ChronoStore, ChronoRecord, WalEvent` | `from chronomemory import ChronoStore, ChronoRecord, WalEvent` |
| `from specsmith.esdb.bridge import EsdbBridge, EsdbRecord` | `from chronomemory import EsdbBridge` / `from chronomemory.bridge import EsdbRecord` |
| `from specsmith.esdb.store import open_store` | `from chronomemory import open_store` |

### 3. Verify WAL compatibility

The WAL format is identical — no data migration needed:

```python
from chronomemory import ChronoStore
with ChronoStore("/path/to/project") as store:
    assert store.chain_valid()
    print(f"Migrated {store.record_count()} records")
```

### 4. Remove vendored code (specsmith)

```bash
rm src/specsmith/esdb/store.py
rm src/specsmith/esdb/bridge.py
rm src/specsmith/esdb/__init__.py
```

---

## Migrating from .specsmith/ JSON to ESDB

Projects using specsmith ≤ 0.11.2 store requirements and test cases as flat JSON files. Migrate to ESDB to gain OEA fields, tamper-evidence, and confidence-filtered RAG.

### Option A: Python

```python
from chronomemory import ChronoStore
from pathlib import Path

with ChronoStore("/path/to/project") as store:
    counts = store.migrate_from_json(Path("/path/to/project/.specsmith"))
    print(counts)
```

### Option B: specsmith CLI

```bash
cd /path/to/project
specsmith esdb migrate
specsmith esdb status
```

### What gets migrated

| Source file | ESDB kind | ESDB source_type |
|-------------|-----------|------------------|
| `.specsmith/requirements.json` | `requirement` | `observed` |
| `.specsmith/testcases.json` | `testcase` | `observed` |

Governance status mapping:

| Governance status | ESDB status |
|-------------------|-------------|
| `defined`, `implemented`, `planned`, `partial`, `accepted`, `verified`, `<any other>` | `active` |
| `deprecated` | `deprecated` |

!!! note "Status concepts are different"
    Governance status describes where a requirement sits in the development lifecycle. ESDB status describes whether the record is live in the audit trail. They are **separate concepts** that coexist on the same record.

### Idempotency

Migration is idempotent. Running it multiple times on the same `.specsmith/` directory skips records whose `id`, `label`, and `status` already match existing ESDB records.

---

## Troubleshooting

### `chain_valid()` returns False after migration

This can happen if:
- The WAL was modified outside of chronomemory
- A previous migration was interrupted mid-write
- The store was opened with an incompatible format (e.g., the Rust binary WAL)

**Recovery**: delete `.chronomemory/events.wal` and `snapshot.json`, then re-run `migrate_from_json()`. You will lose any ESDB-native records written since the last backup.

### Records missing after reopen

If records are missing after closing and reopening the store:
1. Check `chain_valid()` — if False, the WAL may be corrupt
2. Check the snapshot: `cat .chronomemory/snapshot.json | python -m json.tool | grep seq`
3. Check WAL event count: `wc -l .chronomemory/events.wal`

If `snapshot.seq > wal_event_count`, the snapshot is ahead of the WAL (this can happen if the snapshot was written but the WAL was truncated). Delete the snapshot and reopen.

### `chain_valid()` returns False after compact()

This should not happen with chronomemory ≥ 0.1.0 (fixed in the compact genesis-reset). If you see this on an older vendored version, upgrade to the standalone chronomemory package.

# Integration — specsmith

[specsmith](https://github.com/BitConcepts/specsmith) uses chronomemory as its governance store — requirements, test cases, decisions, and session records live in ESDB.

## Current state

specsmith ≥ 0.11.3 ships with a vendored copy of `specsmith.esdb.store` and `specsmith.esdb.bridge`. This is the **pre-extraction** version of chronomemory. The migration to the standalone `chronomemory` package is planned for specsmith 1.0.

## Migration plan (specsmith → chronomemory)

### Step 1: Add dependency

In specsmith's `pyproject.toml`:

```toml
[project.dependencies]
# ... existing deps ...
chronomemory = { git = "https://github.com/layer1labs/chronomemory.git" }
```

### Step 2: Update imports

```python
# Before (specsmith vendored)
from specsmith.esdb.store import ChronoStore, ChronoRecord
from specsmith.esdb.bridge import EsdbBridge

# After (standalone package)
from chronomemory import ChronoStore, ChronoRecord, EsdbBridge
```

### Step 3: Remove vendored code

Delete `src/specsmith/esdb/store.py`, `src/specsmith/esdb/bridge.py`, and `src/specsmith/esdb/__init__.py`.

### Step 4: Verify WAL compatibility

Existing `.chronomemory/events.wal` files written by the vendored code use the same NDJSON format and SHA-256 hash algorithm. They are fully compatible with the standalone `chronomemory` package:

```python
from chronomemory import ChronoStore
with ChronoStore("/path/to/specsmith-project") as store:
    assert store.chain_valid()
    print(f"Records: {store.record_count()}")
```

## CLI commands

specsmith's `specsmith esdb *` CLI commands delegate to chronomemory:

| Command | Description |
|---------|-------------|
| `specsmith esdb migrate` | Import `.specsmith/*.json` → ESDB WAL |
| `specsmith esdb status` | Show backend, record count, chain validity |
| `specsmith esdb query --kind fact` | List records by kind |
| `specsmith esdb compact` | Write snapshot, truncate WAL |
| `specsmith esdb backup` | Timestamped backup of `.chronomemory/` |
| `specsmith esdb chain-verify` | Verify SHA-256 chain |

## Session records

specsmith writes session records during governed agent sessions:

```python
store.upsert(ChronoRecord(
    id=f"session-{session_id}",
    kind="decision",
    label=f"Agent session: {task_description}",
    source_type="synthetic",
    confidence=float(outcome.confidence),
    model_assumptions={
        "provider": provider,
        "model": model,
    },
    recursion_depth=recursion_depth,
    data={
        "work_item_id": work_item_id,
        "requirement_ids": requirement_ids,
        "outcome": outcome.to_dict(),
    },
))
```

## Governance requirements in ESDB

After `specsmith esdb migrate`, requirements from `.specsmith/requirements.json` are imported as `kind="requirement"` records and accessible to any tool that opens the ESDB:

```python
from chronomemory import EsdbBridge

bridge = EsdbBridge(project_dir=".")
reqs = bridge.requirements()
for r in reqs:
    print(f"{r.id}: {r.label} (confidence={r.confidence})")
```

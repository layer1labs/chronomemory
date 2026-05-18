# Rust Core (Phase 2)

The `crates/chronomemory/` directory contains a more advanced Rust implementation of the ESDB engine. This page documents its capabilities, current status, and the Phase 2 PyO3 bindings plan.

## What the Rust core adds

Beyond the Python implementation, the Rust core includes:

| Feature | Python | Rust |
|---------|--------|------|
| WAL + hash chain | ✅ NDJSON | ✅ Binary (bincode) |
| Snapshot + replay | ✅ | ✅ |
| Confidence-filtered query | ✅ | ✅ |
| Tombstone semantics | ✅ | ✅ |
| **Dependency graph** | ❌ | ✅ `DepGraph` with typed edges |
| **CPSC projection engine** | ❌ | ✅ Accept/Reject/Downgrade decisions |
| **Rollback with cascade** | ❌ | ✅ Propagates to transitive dependents |
| **Context pack compiler** | ❌ | ✅ Token-budget-aware context assembly |
| **Token metrics** | ❌ | ✅ Per-task input/output/tool tracking |
| **Stop conditions** | ❌ | ✅ Automated drift/loop detection |
| **Confidence decay** | ❌ | ✅ On rollback cascade |

## Phase 2 plan

### Step 1: Migrate WAL format to NDJSON

**Blocker**: The Rust WAL currently uses binary bincode format (with `ESDB_WAL` magic header), which is **incompatible** with the Python NDJSON format required by ESDB-Specification.md §2.4.

Migration required:
- Replace `bincode::serialize` with `serde_json::to_string`
- Remove `WAL_MAGIC` binary header
- Change per-entry encoding to one JSON object per line
- Update `SHA256(prev_hash_bytes || payload_bytes)` to match Python's `SHA256(prev_hash_str || canonical_json(payload))`

After this, WAL files written by Rust are readable by Python and vice versa.

### Step 2: Add PyO3 Python bindings

```toml
# crates/chronomemory/Cargo.toml (Phase 2)
[lib]
name = "chronomemory"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.21", features = ["extension-module"] }
```

Exposed Python API (matches Python implementation):
```python
# Phase 2: uses Rust engine when available
from chronomemory import ChronoStore, ChronoRecord

# Falls back to Python if Rust wheel not available
```

### Step 3: Switch build system to maturin

```toml
# pyproject.toml (Phase 2)
[build-system]
requires = ["maturin>=1.4"]
build-backend = "maturin"

[tool.maturin]
python-source = "src"
features = ["pyo3/extension-module"]
```

### Step 4: Expose Rust-only features to Python

The dependency graph and rollback engine are not in the Python implementation. Phase 2 exposes them:

```python
# Phase 2 API (Rust-only features)
from chronomemory import ChronoStore

with ChronoStore(project_root) as store:
    # Dependency graph
    store.add_edge(record_a_id, record_b_id, edge_type="DependsOn")

    # Rollback with cascade
    result = store.rollback(record_id, reason="root fact was wrong")
    print(result.invalidated_ids)    # all transitively dependent records
    print(result.confidence_degraded)  # records with decayed confidence

    # Context pack (token-budget-aware)
    pack = store.context_pack(task_id=task_id, token_budget=4000)
    print(pack.entries)   # highest-priority records within budget
    print(pack.token_count)

    # Projection (CPSC anti-hallucination at storage time)
    decision = store.project(proposal)
    if decision == "Accept":
        store.commit(record)
```

## Rust crate status

The Rust crate has **20 integration tests** (`crates/chronomemory/tests/esdb_tests.rs`) covering:

- TEST-ESDB-001: WAL hash chain integrity
- TEST-ESDB-002: WAL replay produces identical state
- TEST-ESDB-003: Projection accepts sourced facts
- TEST-ESDB-004: Projection rejects unsupported claims (anti-hallucination)
- TEST-ESDB-005: Contradiction detection
- TEST-ESDB-006: Duplicate work detection
- TEST-ESDB-007: Dependency graph traversal
- TEST-ESDB-008: Rollback propagates to transitive dependents
- TEST-ESDB-009: No-forgetfulness (invalidated records stay visible)
- TEST-ESDB-010: Context pack excludes invalidated records
- TEST-ESDB-011: Context pack respects token budget
- TEST-ESDB-012: Token metrics recorded per task
- TEST-ESDB-013: Confidence decay on rollback
- TEST-ESDB-014: Record status transitions
- TEST-ESDB-015–020: Query, stop conditions, metrics

```bash
# Run Rust tests
cd crates/chronomemory
cargo test
```

Note: TEST-ESDB-002 is currently marked `#[ignore]` pending a data field migration from `serde_json::Value` to raw bytes for cross-session replay.

## Building the Rust crate

```bash
# Requires Rust toolchain
rustup install stable
cargo build --release --manifest-path crates/chronomemory/Cargo.toml
```

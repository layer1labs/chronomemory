# Context Budget

## Project context

**Project:** chronomemory
**Type:** python-library
**Platforms:** Windows, Linux, macOS
**Phase:** see `specsmith phase status`
**Spec:** ESDB-Specification.md v1.0 (Layer1Labs / BitConcepts)

### What this project is

chronomemory is the **Epistemic State Database (ESDB)** — a zero-dependency Python
library providing tamper-evident, WAL-based persistence for agentic AI workflows.

Every record (`ChronoRecord`) carries 7 mandatory OEA anti-hallucination fields:
`source_type`, `confidence`, `evidence`, `epistemic_boundary`, `is_hypothesis`,
`model_assumptions`, `recursion_depth`. The WAL (`events.wal`) is SHA-256 chained
NDJSON; `chain_valid()` detects any post-write tampering.

### Key invariants an agent MUST NOT violate

1. **Zero runtime dependencies** — `pyproject.toml` `dependencies = []` is a hard
   constraint (REQ-CM-009). Never add runtime deps.
2. **NDJSON WAL format** — Do not change the WAL to binary. NDJSON is canonical.
3. **OEA fields are mandatory** — Safe defaults exist; do not remove fields from
   `ChronoRecord`.
4. **Tests must stay green** — `pytest tests/ -v` must pass on Python 3.10–3.13,
   Linux and Windows.
5. **Ruff clean** — `ruff check src/ tests/` must produce zero errors.

### Source layout

```
src/chronomemory/
  __init__.py    — public API surface
  store.py       — ChronoStore, ChronoRecord, WalEvent
  bridge.py      — EsdbBridge, EsdbRecord, EsdbStatus
crates/chronomemory/  — Rust core (Phase 2, not yet integrated)
tests/
  test_store.py, test_wal_chain.py, test_oea.py
  test_query.py, test_robustness.py, test_bridge.py
docs/
  ARCHITECTURE.md, SPECSMITH.yml, architecture/
```

### Development workflow

```bash
pip install -e ".[dev]"
pytest tests/ -v             # run all 113 tests
ruff check src/ tests/       # lint (must be clean)
mypy src/chronomemory/       # type-check
```

### specsmith CLI quick reference

| Command | Purpose |
--------|--------|
| `specsmith preflight "<intent>"` | Gate any change; get work item ID |
| `specsmith phase show` | Current phase + readiness % |
| `specsmith phase next` | Advance to next AEE phase |
| `specsmith audit` | Full governance health check |
| `specsmith import` | Import requirements from ESDB |
| `specsmith trace seal decision "<msg>"` | Record architectural decision |
| `specsmith serve` | Start REST API on port 7700 |


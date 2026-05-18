# chronomemory

**Epistemic State Database (ESDB) for agentic AI workflows.**

[![GitHub](https://img.shields.io/badge/github-layer1labs%2Fchronomemory-8b5cf6?logo=github)](https://github.com/layer1labs/chronomemory)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Dependencies](https://img.shields.io/badge/runtime%20deps-none-brightgreen)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-113%20passing-brightgreen)](tests/)
[![Docs](https://img.shields.io/badge/docs-ReadTheDocs-blueviolet)](https://chronomemory.readthedocs.io)

---

## Why chronomemory?

Traditional databases store **facts**. Agentic AI systems produce **beliefs** — and beliefs have properties that facts do not:

- **Provenance** — was this observed by a sensor, inferred by logic, or hallucinated by an LLM?
- **Confidence** — how strongly is this held? Is it safe to inject into RAG context?
- **Recursion depth** — was this produced by an agent acting on another agent's output?
- **Tamper-evidence** — if someone edits a past belief to hide a mistake, will you know?

chronomemory makes these properties **mandatory on every record** and uses a SHA-256 hash chain to make every past write tamper-evident.

---

## 30-second example

```python
from chronomemory import ChronoStore, ChronoRecord

with ChronoStore("/path/to/project") as store:

    # Write a benchmark result with full epistemic provenance
    store.upsert(ChronoRecord(
        id="bench-A-seed42",
        kind="fact",
        label="CTT achieves 0% invalid rollout rate on DoorKey-5x5",
        source_type="observed",   # H19 — was this measured or inferred?
        confidence=1.0,            # H17 — degree of belief (0.0–1.0)
        evidence=["seed=42", "epoch=50", "model=CTTStateNet"],  # H20
        epistemic_boundary=["model:CTTStateNet-v1", "dataset:DoorKey-5x5"],  # H15
        data={"invalid_rate": 0.0, "nll_bits": 0.312},
    ))

    # Confidence-filtered RAG query — H18 enforced
    context = store.query(rag_filter=True)   # confidence >= 0.6 only

    # Tamper detection
    assert store.chain_valid()   # False if any past event was modified
```

---

## Installation

```bash
# From GitHub (PyPI release pending)
pip install git+https://github.com/layer1labs/chronomemory.git

# Editable local install
git clone https://github.com/layer1labs/chronomemory.git
pip install -e chronomemory
```

Add to `pyproject.toml`:
```toml
dependencies = [
    "chronomemory @ git+https://github.com/layer1labs/chronomemory.git",
]
```

**Zero runtime dependencies** — pure Python stdlib (`hashlib`, `json`, `os`, `shutil`, `pathlib`).

---

## OEA anti-hallucination fields

Every `ChronoRecord` carries 7 mandatory OEA (Ontological Epistemic Anchoring) fields. Safe defaults apply when omitted.

| Field | Rule | Default | Description |
|-------|------|---------|-------------|
| `source_type` | H19 | `"observed"` | `observed` \| `inferred` \| `hypothesis` \| `synthetic` |
| `confidence` | H17 | `0.7` | Float 0.0–1.0. RAG threshold: `>= 0.6` |
| `evidence` | H20 | `[]` | Source references (doc IDs, URLs, experiment IDs) |
| `epistemic_boundary` | H15 | `[]` | Scope constraints on validity |
| `is_hypothesis` | H20 | `False` | True = tentative, untested belief |
| `model_assumptions` | H21 | `{}` | `{provider, model, temperature, context_window}` |
| `recursion_depth` | H16 | `0` | 0 = human; N = agent chain depth |

`query(rag_filter=True)` returns only records with `confidence >= 0.6` AND `status == "active"` (H18).

---

## Core API

### ChronoStore

```python
from chronomemory import ChronoStore, ChronoRecord

# Context manager (recommended)
with ChronoStore("/path/to/project", recursion_depth=0) as store:
    ...

# Manual lifecycle
store = ChronoStore(project)
store.open()
store.upsert(record)          # write to WAL
records = store.query()       # read from memory
store.delete("FACT-001")      # tombstone (never physical deletion)
assert store.chain_valid()    # verify SHA-256 chain
store.compact()               # truncate WAL → snapshot + 1 sentinel
store.close()
```

**All query parameters:**

```python
store.query(
    kind="fact",           # filter by kind (None = all)
    status="active",       # "active" | "deprecated" | "tombstone" | "" (all)
    rag_filter=True,       # H18: confidence >= 0.6 only
    min_confidence=0.9,    # custom threshold (takes max with rag_filter)
)
```

### ChronoRecord kinds

`fact` · `hypothesis` · `requirement` · `testcase` · `decision` · `risk`

### EsdbBridge

Unified adapter: delegates to `ChronoStore` when `.chronomemory/events.wal` exists; falls back to `.specsmith/*.json` for uninitialized projects.

```python
from chronomemory import EsdbBridge

bridge = EsdbBridge(project_dir=".")
print(bridge.status().to_dict())   # backend, record_count, chain_valid, wal_seq
reqs  = bridge.requirements()      # list[EsdbRecord]
tests = bridge.testcases()          # list[EsdbRecord]
```

---

## Where data lives

```
<project_root>/
  .chronomemory/
    events.wal        ← append-only NDJSON, SHA-256 chained
    snapshot.json     ← materialized state (every 50 events)
    backup/
      20260518T170000/  ← timestamped backup
```

The WAL is NDJSON — human-readable, grep-able, diff-able, no special tooling needed:

```bash
cat .chronomemory/events.wal | python -m json.tool
grep '"op": "upsert"' .chronomemory/events.wal | wc -l
```

---

## Migration from .specsmith/ JSON

Projects using specsmith store requirements and test cases as flat JSON. Migrate to ESDB to gain OEA fields and tamper-evidence:

```python
from chronomemory import ChronoStore
from pathlib import Path

with ChronoStore("." ) as store:
    counts = store.migrate_from_json(Path(".specsmith"))
    print(counts)  # {'requirements': 12, 'testcases': 10, 'skipped': 0}
```

Or: `specsmith esdb migrate` (requires specsmith ≥ 0.11.3)

**Import map:**
```
# Before (specsmith vendored)
from specsmith.esdb.store import ChronoStore, ChronoRecord
from specsmith.esdb.bridge import EsdbBridge

# After (standalone)
from chronomemory import ChronoStore, ChronoRecord, EsdbBridge
```

WAL format is identical — existing `.chronomemory/events.wal` files are fully compatible.

---

## Integration

### chronoagent — memory write gate + RAG source

```python
# chronoagent/memory/store.py
from chronomemory import ChronoStore, ChronoRecord

class AgentMemoryStore:
    def __init__(self, project_root: str, agent_depth: int = 1):
        self._store = ChronoStore(project_root, recursion_depth=agent_depth)
        self._store.open()

    def write_belief(self, content: str, confidence: float = 0.7, evidence=None) -> str:
        """Called by memory_write_gate after gate passes."""
        import uuid
        rid = str(uuid.uuid4())
        self._store.upsert(ChronoRecord(
            id=rid, kind="fact", label=content,
            source_type="inferred", confidence=confidence,
            evidence=evidence or [],
        ))
        return rid

    def rag_context(self) -> list[dict]:
        """Confidence-filtered beliefs for CPR retrieval gate."""
        return [
            {"chunk_id": r.id, "content": r.label,
             "authority_score": r.confidence, "source_type": r.source_type}
            for r in self._store.query(rag_filter=True)
        ]
```

### ctt-neural — benchmark results + hypothesis tracking

```python
# Persist benchmark result with patent-quality provenance
from chronomemory import ChronoStore, ChronoRecord

with ChronoStore(project_root, recursion_depth=0) as store:
    store.upsert(ChronoRecord(
        id=f"bench-{scenario}-seed{seed}",
        kind="fact",
        label=f"CTT on {scenario}: invalid_rate={result['invalid_rate']}",
        source_type="observed",
        confidence=1.0,
        evidence=[f"seed={seed}", f"model={model_id}", f"epoch={epoch}"],
        data=result,
    ))
    assert store.chain_valid()   # tamper-evident proof for patent filing

# Track hypotheses through lifecycle
store.upsert(ChronoRecord(
    id="HYP-001", kind="hypothesis",
    label="CTT R=4 NLL within 2% of Bayes-optimal on scenario B",
    is_hypothesis=True, confidence=0.75,
    source_type="inferred",
    evidence=["REQ-NN-006", "CTT-Paper §4.2"],
))
# After experiment: rec.is_hypothesis=False, rec.confidence=1.0, store.upsert(rec)
```

### specsmith — governance store

```python
# specsmith reads requirements/testcases via EsdbBridge
from chronomemory import EsdbBridge

bridge = EsdbBridge(project_dir=".")
reqs = bridge.requirements()   # ESDB WAL or .specsmith/ JSON fallback
```

---

## Python vs Rust

| | Python (`src/chronomemory/`) | Rust (`crates/chronomemory/`) |
|---|---|---|
| **Status** | ✅ Production-ready | 🔧 Phase 2 (bindings pending) |
| **WAL format** | NDJSON (canonical) | Binary bincode (needs migration) |
| **Deps** | stdlib only | serde, sha2, uuid, chrono |
| **Dep graph** | ❌ | ✅ typed edges |
| **Projection engine** | ❌ | ✅ CPSC Accept/Reject/Downgrade |
| **Rollback cascade** | ❌ | ✅ transitive invalidation |
| **Context pack** | ❌ | ✅ token-budget assembly |
| **PyO3 bindings** | — | Phase 2 |

**Phase 2**: migrate Rust WAL to NDJSON → add PyO3 bindings → `from chronomemory import ChronoStore` transparently uses Rust with Python fallback.

---

## Test suite

113 tests, all passing on Python 3.10–3.13 (Linux + Windows):

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Test categories:
- **test_store.py** — snapshot replay, tombstone, migration, zero-deps
- **test_wal_chain.py** — hash chain integrity, NDJSON format, atomic writes, cross-project compat
- **test_oea.py** — all 7 OEA fields, WAL round-trip, recursion depth stamping
- **test_query.py** — confidence filtering, RAG threshold, kind/status filters
- **test_robustness.py** — 60+ tests: WAL corruption at multiple offsets, hash tampering, binary garbage, snapshot gaps, write failure simulation, crash recovery, CRLF, Unicode, Arabic RTL, 100KB payloads, compact/backup/lifecycle
- **test_bridge.py** — EsdbBridge delegation, JSON fallback, write operations

---

## Docs

Full documentation at **[chronomemory.readthedocs.io](https://chronomemory.readthedocs.io)**:

- [Installation](https://chronomemory.readthedocs.io/installation)
- [Quick start](https://chronomemory.readthedocs.io/quickstart)
- [Concepts: OEA fields](https://chronomemory.readthedocs.io/concepts/oea)
- [Concepts: WAL and hash chain](https://chronomemory.readthedocs.io/concepts/wal)
- [API: ChronoStore](https://chronomemory.readthedocs.io/api/store)
- [API: ChronoRecord](https://chronomemory.readthedocs.io/api/record)
- [API: EsdbBridge](https://chronomemory.readthedocs.io/api/bridge)
- [Integration: chronoagent](https://chronomemory.readthedocs.io/integration/chronoagent)
- [Integration: ctt-neural](https://chronomemory.readthedocs.io/integration/ctt-neural)
- [Integration: specsmith](https://chronomemory.readthedocs.io/integration/specsmith)
- [Migration guide](https://chronomemory.readthedocs.io/migration)
- [Rust core (Phase 2)](https://chronomemory.readthedocs.io/rust-core)

---

## Spec

Implements **ESDB-Specification.md v1.0** (Layer1Labs / BitConcepts, proprietary).

Part of the Layer1Labs IP stack: CPSC · CAS-YAML · CPSC-RAG · CTT · ChronoFabric Gen 2.

---

© 2026 Layer1Labs Silicon, Inc. / BitConcepts, LLC. — MIT License.

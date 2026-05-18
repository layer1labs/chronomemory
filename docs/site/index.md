# chronomemory

**Epistemic State Database (ESDB) for agentic AI workflows.**

[![GitHub](https://img.shields.io/badge/github-layer1labs%2Fchronomemory-purple)](https://github.com/layer1labs/chronomemory)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/layer1labs/chronomemory/blob/main/LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen)](https://github.com/layer1labs/chronomemory/blob/main/pyproject.toml)

---

## What is chronomemory?

Traditional databases store **facts**. Agentic AI systems produce **beliefs** — and beliefs have properties that facts do not:

- *Who or what produced this?* Was it a human, an LLM at temperature 0.7, or an agent acting on other agent output?
- *How confident is the system?* Should this belief be injected into RAG context or kept below the confidence threshold?
- *What evidence supports it?* Is this observation-backed or speculative?
- *Can it be tampered with?* If someone modifies a past belief to cover up a hallucination, will you know?

chronomemory answers all four questions by making **provenance, confidence, evidence, and tamper-evidence** first-class on every stored record.

---

## Core features

| Feature | Description |
|---------|-------------|
| **OEA fields** | 7 mandatory Ontological Epistemic Anchoring fields on every record (H15–H22) |
| **SHA-256 hash chain** | Every WAL event links to the previous — any tampering is detectable |
| **Confidence-filtered RAG** | `query(rag_filter=True)` returns only records with `confidence >= 0.6` (H18) |
| **NDJSON WAL** | Human-readable, grep-able, diff-able write-ahead log |
| **Zero dependencies** | Pure Python stdlib — `pip install chronomemory` with no transitive deps |
| **Snapshot + tail replay** | Fast startup: load snapshot, replay only the new tail |
| **Tombstone semantics** | `delete()` never physically removes records — audit trail stays intact |

---

## 30-second example

```python
from chronomemory import ChronoStore, ChronoRecord

with ChronoStore("/path/to/project") as store:
    # Write a fact with full epistemic provenance
    store.upsert(ChronoRecord(
        id="bench-A-001",
        kind="fact",
        label="CTT achieves 0% invalid rollout rate on DoorKey",
        source_type="observed",        # H19: was this measured or inferred?
        confidence=1.0,                # H17: degree of belief (0.0–1.0)
        evidence=["seed=42", "epoch=50", "model=CTTStateNet"],  # H20
        data={"invalid_rate": 0.0, "nll": 0.312},
    ))

    # Confidence-filtered RAG query — safe for LLM context injection
    context = store.query(rag_filter=True)   # only confidence >= 0.6

    # Tamper detection
    assert store.chain_valid()
```

---

## Projects using chronomemory

| Project | Role |
|---------|------|
| [specsmith](https://github.com/BitConcepts/specsmith) | Governance store — requirements, test cases, session records |
| [chronoagent](https://github.com/layer1labs/chronoagent) | Memory write gate backing store; RAG retrieval source |
| [ctt-neural](https://github.com/layer1labs/ctt-neural) | Benchmark result store; hypothesis tracking; CPSC audit trail |

---

## Spec reference

Implements [ESDB-Specification.md v1.0](https://github.com/layer1labs/chronomemory/blob/main/docs/architecture/ARCHITECTURE.md) (Layer1Labs / BitConcepts, proprietary).

---

## Navigation

- **[Installation](installation.md)** — pip, git, editable installs
- **[Quick start](quickstart.md)** — end-to-end walkthrough
- **[Concepts → OEA fields](concepts/oea.md)** — the 7 anti-hallucination fields explained
- **[Concepts → WAL and hash chain](concepts/wal.md)** — how tamper-evidence works
- **[API → ChronoStore](api/store.md)** — complete method reference
- **[API → ChronoRecord](api/record.md)** — record dataclass reference
- **[API → EsdbBridge](api/bridge.md)** — unified adapter with legacy fallback
- **[Integration → chronoagent](integration/chronoagent.md)**
- **[Integration → ctt-neural](integration/ctt-neural.md)**
- **[Integration → specsmith](integration/specsmith.md)**
- **[Migration guide](migration.md)** — from `.specsmith/` JSON to ESDB
- **[Rust core (Phase 2)](rust-core.md)** — PyO3 bindings roadmap

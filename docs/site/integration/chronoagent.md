# Integration — chronoagent

[chronoagent](https://github.com/layer1labs/chronoagent) is the world's first CTT-governed agent LLM. chronomemory serves two roles in its architecture.

## Role 1: Memory write gate backing store

chronoagent's `memory_write_gate` gates every write to persistent memory. When the gate passes, the record is written to the project's ESDB store via chronomemory.

```python
# chronoagent/memory/store.py
from chronomemory import ChronoStore, ChronoRecord
from pathlib import Path

class AgentMemoryStore:
    def __init__(self, project_root: str, recursion_depth: int = 0):
        self._store = ChronoStore(project_root, recursion_depth=recursion_depth)
        self._store.open()

    def write_belief(
        self,
        content: str,
        source_type: str = "inferred",
        confidence: float = 0.7,
        evidence: list[str] | None = None,
        record_id: str | None = None,
    ) -> str:
        """Write a belief to ESDB after memory_write_gate passes."""
        import uuid
        rid = record_id or str(uuid.uuid4())
        self._store.upsert(ChronoRecord(
            id=rid,
            kind="fact",
            label=content,
            source_type=source_type,
            confidence=confidence,
            evidence=evidence or [],
        ))
        return rid

    def query_beliefs(self, rag_filter: bool = True) -> list[ChronoRecord]:
        """Return beliefs safe for RAG context injection (H18)."""
        return self._store.query(rag_filter=rag_filter)
```

## Role 2: RAG retrieval source

The CPR (Constraint-Projected Retrieval) gate in chronoagent uses chronomemory as the source of truth for high-confidence facts that can be injected into LLM context:

```python
# chronoagent/rag/esdb_source.py
from chronomemory import ChronoStore, ChronoRecord

def get_rag_context(project_root: str, kind: str | None = None) -> list[dict]:
    """Pull confidence-filtered ESDB records as CPR candidates."""
    with ChronoStore(project_root) as store:
        records = store.query(rag_filter=True, kind=kind)

    return [
        {
            "chunk_id": r.id,
            "content": r.label,
            "authority_score": r.confidence,  # maps to CPR authority score
            "source_type": r.source_type,
            "evidence": r.evidence,
        }
        for r in records
    ]
```

## Installation in chronoagent

Add to `chronoagent/pyproject.toml` or `requirements.txt`:

```toml
# pyproject.toml
[project.dependencies]
chronomemory = { git = "https://github.com/layer1labs/chronomemory.git" }
```

## CTT agent state: `memory_state`

chronoagent's 9-dimension `AgentCTTState` includes a `memory_state` dimension that tracks reads and writes within a session. ESDB is the cross-session persistence backing this dimension:

| Session scope | `memory_state` |
|---------------|----------------|
| Cross-session persistence | ESDB (chronomemory) |

## OEA fields for agent-written beliefs

When an agent writes a belief via `memory_write_gate`, the OEA fields should reflect:

```python
ChronoRecord(
    source_type="inferred",           # Agent derived this, not directly observed
    confidence=0.7,                   # Default; agent may adjust
    recursion_depth=agent_depth,      # Set by ChronoStore(recursion_depth=N)
    model_assumptions={
        "provider": llm_provider,
        "model": llm_model,
        "session_id": session_id,
    },
)
```

## Replaying sessions

Because ESDB has a tamper-evident hash chain, chronoagent session replays can verify that the memory state at any point in time was not altered after the fact:

```python
with ChronoStore(project_root) as store:
    # Verify all beliefs written during this session are intact
    assert store.chain_valid()

    # Retrieve beliefs written at or before a specific session step
    session_beliefs = store.replay(from_seq=session_start_seq)
```

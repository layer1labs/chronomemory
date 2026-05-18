# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Layer1Labs Silicon, Inc. / BitConcepts, LLC.
"""chronomemory — Epistemic State Database for agentic AI workflows.

Quick start::

    from chronomemory import ChronoStore, ChronoRecord

    with ChronoStore("/path/to/project") as store:
        store.upsert(ChronoRecord(
            id="FACT-001",
            kind="fact",
            label="CPSC projection is the sole validity authority",
            source_type="observed",
            confidence=0.99,
            evidence=["CPSC-Specification.md §9"],
        ))

        facts = store.query(kind="fact", rag_filter=True)

Spec: ESDB-Specification.md v1.0 (Layer1Labs / BitConcepts)
"""
from chronomemory.store import (
    ChronoRecord,
    ChronoStore,
    WalEvent,
    open_store,
)
from chronomemory.bridge import (
    EsdbBridge,
    EsdbRecord,
    EsdbStatus,
)

__version__ = "0.1.0"
__all__ = [
    # Core store
    "ChronoStore",
    "ChronoRecord",
    "WalEvent",
    "open_store",
    # Bridge (unified read/write with .specsmith/ fallback)
    "EsdbBridge",
    "EsdbRecord",
    "EsdbStatus",
]

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Layer1Labs Silicon, Inc. / BitConcepts, LLC.
"""chronomemory — Epistemic State Database for agentic AI workflows.

Optional Rust acceleration:
    Build the Rust extension with maturin to enable a faster backend::

        pip install maturin
        maturin develop --manifest-path crates/chronomemory-py/Cargo.toml

    When the ``_chronomemory_rust`` extension is present it is imported
    automatically and ``RUST_BACKEND`` is set to ``True``.

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

# ---------------------------------------------------------------------------
# Optional Rust acceleration
# ---------------------------------------------------------------------------
# Try to import the PyO3-compiled extension module. If unavailable (e.g. the
# Rust extension has not been built yet), fall back silently to pure Python.
# Build with: maturin develop --manifest-path crates/chronomemory-py/Cargo.toml
from typing import Any

from chronomemory.bridge import (
    EsdbBridge,
    EsdbRecord,
    EsdbStatus,
)
from chronomemory.context_pack import ContextPack, ContextPackCompiler, ContextPackEntry
from chronomemory.deps import DependencyEdge, DepGraph
from chronomemory.rollback import RollbackReport, invalidate
from chronomemory.store import (
    ChronoRecord,
    ChronoStore,
    WalEvent,
    open_store,
)

RustChronoStore: Any | None = None
RustRecord: Any | None = None
RUST_BACKEND: bool = False

try:
    import _chronomemory_rust as _rust  # noqa: PLC0415

    RustChronoStore = _rust.RustChronoStore
    RustRecord = _rust.RustRecord
    RUST_BACKEND = True
except ImportError:
    pass

__version__ = "0.1.1"
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
    # Phase 2: dependency graph
    "DepGraph",
    "DependencyEdge",
    # Phase 2: epistemic rollback
    "RollbackReport",
    "invalidate",
    # Phase 2: context pack compiler
    "ContextPack",
    "ContextPackCompiler",
    "ContextPackEntry",
    # Phase 3: optional Rust acceleration
    "RustChronoStore",
    "RustRecord",
    "RUST_BACKEND",
]

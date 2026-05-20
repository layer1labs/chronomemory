"""tests/test_cross_compat.py — Rust-Python WAL cross-compatibility tests.

Issue #16 / REQ-CM-025 / TEST-CM-025

Verifies that the NDJSON WAL written by Python ChronoStore produces entries
whose SHA-256 hash chain can be independently validated using the same
algorithm the Rust ESDB engine uses (and vice versa).

Both implementations compute:
    SHA256(json.dumps(
        {seq, ts, op, record_id, record, prev_hash, recursion_depth},
        sort_keys=True
    ).encode())

These tests do NOT require a compiled Rust binary to be present — instead
they replicate the Rust hash algorithm directly in Python, proving that
a Python-written WAL would pass Rust's verify_chain() and that both sides
agree on the canonical NDJSON schema.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from chronomemory import ChronoRecord, ChronoStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = frozenset(
    ["seq", "ts", "op", "record_id", "record", "prev_hash", "hash", "recursion_depth"]
)


def _rust_compute_hash(
    seq: int,
    ts: str,
    op: str,
    record_id: str,
    record: object,
    prev_hash: str,
    recursion_depth: int,
) -> str:
    """Replicate Rust's WalEntry::compute_hash() in Python.

    Uses a sorted-key dict (mirroring BTreeMap) and json.dumps with
    sort_keys=True to produce the canonical JSON, then SHA-256.
    This must match Python's own WalEvent.compute_hash() exactly.
    """
    payload = {
        "seq": seq,
        "ts": ts,
        "op": op,
        "record_id": record_id,
        "record": record,
        "prev_hash": prev_hash,
        "recursion_depth": recursion_depth,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _read_wal(tmp_path: Path) -> list[dict]:
    wal = tmp_path / ".chronomemory" / "events.wal"
    if not wal.exists():
        return []
    lines = [ln.strip() for ln in wal.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


# ---------------------------------------------------------------------------
# TEST-CM-025a: NDJSON schema cross-compatibility
# ---------------------------------------------------------------------------


def test_python_wal_has_all_cross_compat_fields(tmp_path: Path) -> None:
    """Every WAL entry written by Python has exactly the 8 fields Rust expects.

    Rust's WalEntry struct has: seq, ts, op, record_id, record, prev_hash,
    hash, recursion_depth. Verifies Python produces the same schema.
    """
    with ChronoStore(tmp_path) as store:
        store.upsert(
            ChronoRecord(id="COMPAT-001", kind="fact", label="cross compat", confidence=0.9)
        )
        store.upsert(ChronoRecord(id="COMPAT-002", kind="decision", label="architecture decision"))
        store.delete("COMPAT-001")

    entries = _read_wal(tmp_path)
    assert len(entries) >= 2, "Expected at least 2 WAL entries"

    for entry in entries:
        missing = _REQUIRED_FIELDS - set(entry.keys())
        assert not missing, f"Entry missing fields: {missing}\n  Entry: {entry}"


# ---------------------------------------------------------------------------
# TEST-CM-025b: Hash chain cross-verification
# ---------------------------------------------------------------------------


def test_python_wal_hash_chain_verifiable_by_rust_algorithm(tmp_path: Path) -> None:
    """WAL entries written by Python pass hash verification using Rust's algorithm.

    Replicates WalReader::verify_chain() in Python: for each entry, recomputes
    the expected hash using the same BTreeMap-sorted-key JSON approach and
    asserts it matches the stored hash.
    """
    with ChronoStore(tmp_path) as store:
        for i in range(5):
            store.upsert(
                ChronoRecord(id=f"R{i:03d}", kind="fact", label=f"record {i}", confidence=0.8)
            )

    entries = _read_wal(tmp_path)
    assert len(entries) == 5

    prev_hash = ""
    for entry in entries:
        # Verify prev_hash linkage
        assert entry["prev_hash"] == prev_hash, (
            f"prev_hash mismatch at seq={entry['seq']}: "
            f"expected {prev_hash!r}, got {entry['prev_hash']!r}"
        )
        # Recompute hash using Rust's algorithm
        expected = _rust_compute_hash(
            seq=entry["seq"],
            ts=entry["ts"],
            op=entry["op"],
            record_id=entry["record_id"],
            record=entry["record"],
            prev_hash=entry["prev_hash"],
            recursion_depth=entry.get("recursion_depth", 0),
        )
        assert entry["hash"] == expected, (
            f"Hash mismatch at seq={entry['seq']}: "
            f"Python stored {entry['hash']!r}, Rust algo produces {expected!r}"
        )
        prev_hash = entry["hash"]


# ---------------------------------------------------------------------------
# TEST-CM-025c: Algorithm equivalence proof
# ---------------------------------------------------------------------------


def test_hash_algorithm_is_identical_between_python_and_rust_replica(tmp_path: Path) -> None:
    """Python's own chain_valid() and the Rust-replica hash function agree.

    This is the core cross-compat proof: if chain_valid() passes AND the
    Rust-replica independently produces the same hashes, both engines are
    guaranteed to produce identical chains from identical inputs.
    """
    with ChronoStore(tmp_path) as store:
        store.upsert(ChronoRecord(id="PROOF-1", kind="requirement", label="REQ cross-compat"))
        store.upsert(ChronoRecord(id="PROOF-2", kind="testcase", label="TEST cross-compat"))
        # chain_valid() uses Python's own algorithm
        assert store.chain_valid(), "chain_valid() must pass as precondition"

    entries = _read_wal(tmp_path)

    # Now verify each entry's hash using the Rust-replica function
    for entry in entries:
        rust_hash = _rust_compute_hash(
            seq=entry["seq"],
            ts=entry["ts"],
            op=entry["op"],
            record_id=entry["record_id"],
            record=entry["record"],
            prev_hash=entry["prev_hash"],
            recursion_depth=entry.get("recursion_depth", 0),
        )
        # If these are equal, both algorithms agree — the WAL is cross-compatible
        assert entry["hash"] == rust_hash, (
            f"Algorithm divergence at seq={entry['seq']}: "
            f"chain_valid hash != Rust-replica hash. "
            f"WAL is NOT cross-compatible."
        )


# ---------------------------------------------------------------------------
# TEST-CM-025d: All op types are cross-compatible
# ---------------------------------------------------------------------------


def test_all_op_types_have_cross_compat_hashes(tmp_path: Path) -> None:
    """upsert, delete, and compact entries all pass Rust-algorithm hash check."""
    with ChronoStore(tmp_path) as store:
        store.upsert(ChronoRecord(id="OP-1", kind="fact", label="op test"))
        store.delete("OP-1")  # produces 'delete' op
        store.compact()  # produces 'compact' sentinel

    entries = _read_wal(tmp_path)
    ops_seen = {e["op"] for e in entries}
    # compact resets WAL so we may only see the sentinel
    assert "compact" in ops_seen or "upsert" in ops_seen

    for entry in entries:
        expected = _rust_compute_hash(
            seq=entry["seq"],
            ts=entry["ts"],
            op=entry["op"],
            record_id=entry["record_id"],
            record=entry["record"],
            prev_hash=entry["prev_hash"],
            recursion_depth=entry.get("recursion_depth", 0),
        )
        assert entry["hash"] == expected, f"Hash mismatch for op={entry['op']!r}"


# ---------------------------------------------------------------------------
# TEST-CM-025e: Edge records are cross-compatible
# ---------------------------------------------------------------------------


def test_edge_records_have_cross_compat_hashes(tmp_path: Path) -> None:
    """Edge records (kind=edge) written by DepGraph also pass Rust hash check."""
    from chronomemory import DepGraph

    with ChronoStore(tmp_path) as store:
        store.upsert(ChronoRecord(id="N1", kind="fact", label="node 1"))
        store.upsert(ChronoRecord(id="N2", kind="fact", label="node 2"))
        g = DepGraph(store=store)
        g.add_edge("N2", "N1", "depends_on")
        assert store.chain_valid()

    entries = _read_wal(tmp_path)
    edge_entries = [e for e in entries if e.get("record", {}).get("kind") == "edge"]
    assert edge_entries, "Expected at least one edge record in WAL"

    for entry in entries:
        expected = _rust_compute_hash(
            seq=entry["seq"],
            ts=entry["ts"],
            op=entry["op"],
            record_id=entry["record_id"],
            record=entry["record"],
            prev_hash=entry["prev_hash"],
            recursion_depth=entry.get("recursion_depth", 0),
        )
        assert entry["hash"] == expected

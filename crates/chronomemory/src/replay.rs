// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Layer1Labs / BitConcepts, LLC.
//! Replay engine — deterministic state reconstruction from WAL (Invariant 8).

use crate::dependency::DepGraph;
use crate::store::Store;
use crate::types::*;
use crate::wal::{WalEntry, WalReader};

/// Replay result.
#[derive(Debug)]
pub struct ReplayResult {
    pub entries_replayed: u64,
    pub records_materialized: usize,
    pub edges_rebuilt: usize,
    pub chain_valid: bool,
}

/// Replay all WAL entries into a fresh store + dependency graph.
///
/// Determinism guarantee: same WAL → identical materialized state.
pub fn replay_full(
    entries: &[WalEntry],
    store: &mut Store,
    dep_graph: &mut DepGraph,
) -> ReplayResult {
    store.clear();
    dep_graph.clear();

    let mut count = 0u64;

    for entry in entries {
        match entry.op.as_str() {
            "upsert" | "migrate" => {
                if let Ok(record) = serde_json::from_value::<Record>(entry.record.clone()) {
                    store.upsert(record);
                }
            }
            "delete" | "invalidate" => {
                // Parse record_id as EsdbId (UUID) if possible, else skip
                if let Ok(uuid) = entry.record_id.parse::<uuid::Uuid>() {
                    let id = EsdbId(uuid);
                    store.invalidate(&id);
                }
            }
            "add_edge" => {
                if let Ok(edge) = serde_json::from_value::<DepEdge>(entry.record.clone()) {
                    dep_graph.add_edge(edge.from, edge.to, edge.edge_type);
                }
            }
            // rollback, metric, compact are informational — state already changed
            // via individual invalidate/upsert events
            _ => {}
        }
        count += 1;
    }

    ReplayResult {
        entries_replayed: count,
        records_materialized: store.count_total(),
        edges_rebuilt: dep_graph.edge_count(),
        chain_valid: true, // caller should verify separately
    }
}

/// Verify replay integrity: replay from WAL file and compare chain.
pub fn verify_replay(wal_path: &str) -> Result<ReplayResult, crate::wal::WalError> {
    let reader = WalReader::open(wal_path)?;
    let chain_valid = reader.verify_chain()?;
    let entries = reader.read_all()?;

    let mut store = Store::new();
    let mut dep_graph = DepGraph::new();
    let mut result = replay_full(&entries, &mut store, &mut dep_graph);
    result.chain_valid = chain_valid;
    Ok(result)
}

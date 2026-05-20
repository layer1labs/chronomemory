// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Layer1Labs / BitConcepts, LLC.
//! write_wal — cross-compat CI helper: writes N records to a Rust ESDB.
//!
//! Usage: write_wal <output_dir> [n_records]
//!
//! Creates an Esdb at <output_dir>/.chronomemory/, writes N records (default 5),
//! verifies the chain, then prints the output_dir path.
//!
//! The .chronomemory/ subdirectory layout matches Python ChronoStore so that
//! `ChronoStore(<output_dir>).chain_valid()` works directly in CI.

use chronomemory::{
    types::{Record, RecordKind},
    Esdb,
};
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let output_dir = args
        .get(1)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("/tmp/cross_compat"));
    let n: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(5);

    // Write to <output_dir>/.chronomemory/ so Python ChronoStore(<output_dir>)
    // finds the WAL at the expected path: <output_dir>/.chronomemory/events.wal
    let esdb_dir = output_dir.join(".chronomemory");
    let mut db = Esdb::open(&esdb_dir).expect("failed to open ESDB");

    for i in 0..n {
        db.commit(
            Record::new(RecordKind::Fact, format!("cross-compat fact {i}")).with_confidence(0.9),
        )
        .unwrap_or_else(|e| panic!("failed to commit record {i}: {e}"));
    }

    // Self-check: Rust chain must be valid before handing to Python.
    assert!(
        db.verify_chain().expect("verify_chain failed"),
        "Rust chain invalid after write — aborting cross-compat test"
    );

    println!("{}", output_dir.display());
}

// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Layer1Labs / BitConcepts, LLC.
//! Python→Rust cross-compat integration test (TEST-CM-025 / Issue #16).
//!
//! Reads a WAL written by Python ChronoStore and verifies the hash chain
//! using Rust's WalReader::verify_chain().
//!
//! Run in CI via the `cross-compat` job:
//!   CROSS_COMPAT_WAL=/path/to/events.wal \
//!     cargo test --test cross_compat_py_to_rust -- --nocapture
//!
//! Silently skips when CROSS_COMPAT_WAL is unset so that `cargo test --workspace`
//! continues to work without the cross-compat CI setup.

use chronomemory::wal::WalReader;

/// TEST-CM-025 (Python→Rust direction): a WAL written by Python ChronoStore
/// must pass Rust's verify_chain() without modification.
#[test]
fn test_python_wal_passes_rust_verify_chain() {
    let wal_path = match std::env::var("CROSS_COMPAT_WAL") {
        Ok(p) => std::path::PathBuf::from(p),
        Err(_) => {
            eprintln!("CROSS_COMPAT_WAL not set — skipping Python→Rust cross-compat test");
            return;
        }
    };

    assert!(wal_path.exists(), "WAL file not found: {:?}", wal_path);

    let reader = WalReader::open(&wal_path).expect("failed to open WAL reader");

    // Core assertion: Python WAL must pass Rust hash-chain verification.
    let is_valid = reader.verify_chain().expect("verify_chain error");
    assert!(is_valid, "Python WAL failed Rust verify_chain()");

    // Sanity: at least one entry must be present.
    let entries = reader.read_all().expect("failed to read WAL entries");
    assert!(!entries.is_empty(), "expected at least one WAL entry");

    println!("Python→Rust: {} entries validated ✓", entries.len());
}

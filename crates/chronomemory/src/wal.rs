// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Layer1Labs / BitConcepts, LLC.
//! Append-only Write-Ahead Log — NDJSON format with SHA-256 hash chain.
//!
//! Each WAL entry is a single JSON object on one line (Newline-Delimited JSON).
//! The format is cross-compatible with the Python ChronoStore implementation
//! in src/chronomemory/store.py (ESDB-Specification.md §2.4, REQ-CM-002).
//!
//! Hash computation matches Python:
//! `hashlib.sha256(json.dumps({seq,ts,op,record_id,payload,prev_hash}, sort_keys=True).encode()).hexdigest()`

use crate::types::EsdbId;
use chrono::Utc;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

// ---------------------------------------------------------------------------
// WAL entry
// ---------------------------------------------------------------------------

/// A single WAL entry serialised as one NDJSON line.
///
/// Field names match Python's WalEvent exactly for cross-compatibility:
/// seq, ts, op, record_id, record, prev_hash, hash, recursion_depth.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WalEntry {
    pub seq: u64,
    pub ts: String,
    pub op: String,
    pub record_id: String,
    /// The record payload (named 'record' to match Python WalEvent.record)
    pub record: serde_json::Value,
    pub prev_hash: String,
    pub hash: String,
    #[serde(default)]
    pub recursion_depth: u64,
}

impl WalEntry {
    /// Compute the canonical hash for a WAL entry.
    ///
    /// Exactly matches Python's WalEvent.compute_hash():
    /// `SHA256(json.dumps({seq,ts,op,record_id,record,prev_hash,recursion_depth}, sort_keys=True))`
    pub fn compute_hash(
        seq: u64,
        ts: &str,
        op: &str,
        record_id: &str,
        record: &serde_json::Value,
        prev_hash: &str,
        recursion_depth: u64,
    ) -> String {
        let mut map: BTreeMap<&str, serde_json::Value> = BTreeMap::new();
        map.insert("seq", serde_json::json!(seq));
        map.insert("ts", serde_json::json!(ts));
        map.insert("op", serde_json::json!(op));
        map.insert("record_id", serde_json::json!(record_id));
        map.insert("record", record.clone());
        map.insert("prev_hash", serde_json::json!(prev_hash));
        map.insert("recursion_depth", serde_json::json!(recursion_depth));
        let canonical =
            serde_json::to_string(&map).expect("BTreeMap<&str,Value> always serialises");
        let mut hasher = Sha256::new();
        hasher.update(canonical.as_bytes());
        hex::encode(hasher.finalize())
    }
}

// ---------------------------------------------------------------------------
// WAL writer
// ---------------------------------------------------------------------------

pub struct WalWriter {
    path: PathBuf,
    seq: u64,
    prev_hash: String,
}

impl WalWriter {
    /// Open or create an NDJSON WAL file.
    pub fn open(path: impl AsRef<Path>) -> Result<Self, WalError> {
        let path = path.as_ref().to_path_buf();
        if path.exists() {
            let reader = WalReader::open(&path)?;
            let (seq, prev_hash) = reader.last_seq_and_hash()?;
            Ok(Self { path, seq, prev_hash })
        } else {
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent).map_err(WalError::Io)?;
            }
            File::create(&path).map_err(WalError::Io)?;
            Ok(Self {
                path,
                seq: 0,
                prev_hash: String::new(),
            })
        }
    }

    /// Append an event to the WAL.
    pub fn append(
        &mut self,
        op: &str,
        record_id: &EsdbId,
        record: serde_json::Value,
    ) -> Result<WalEntry, WalError> {
        self.seq += 1;
        let ts = Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string();
        let record_id_str = record_id.to_string();
        let recursion_depth: u64 = 0;
        let hash = WalEntry::compute_hash(
            self.seq,
            &ts,
            op,
            &record_id_str,
            &record,
            &self.prev_hash,
            recursion_depth,
        );
        let entry = WalEntry {
            seq: self.seq,
            ts,
            op: op.to_owned(),
            record_id: record_id_str,
            record,
            prev_hash: self.prev_hash.clone(),
            hash: hash.clone(),
            recursion_depth,
        };
        let line = serde_json::to_string(&entry).map_err(WalError::Serialize)?;
        let mut file = OpenOptions::new()
            .append(true)
            .open(&self.path)
            .map_err(WalError::Io)?;
        file.write_all(line.as_bytes()).map_err(WalError::Io)?;
        file.write_all(b"\n").map_err(WalError::Io)?;
        file.flush().map_err(WalError::Io)?;
        self.prev_hash = hash;
        Ok(entry)
    }

    pub fn seq(&self) -> u64 {
        self.seq
    }

    pub fn prev_hash(&self) -> &str {
        &self.prev_hash
    }
}

// ---------------------------------------------------------------------------
// WAL reader
// ---------------------------------------------------------------------------

pub struct WalReader {
    path: PathBuf,
}

impl WalReader {
    pub fn open(path: impl AsRef<Path>) -> Result<Self, WalError> {
        let path = path.as_ref().to_path_buf();
        if !path.exists() {
            return Err(WalError::NotFound(path.display().to_string()));
        }
        Ok(Self { path })
    }

    /// Read all valid NDJSON entries, silently skipping blank lines and malformed JSON.
    pub fn read_all(&self) -> Result<Vec<WalEntry>, WalError> {
        let file = File::open(&self.path).map_err(WalError::Io)?;
        let reader = BufReader::new(file);
        let mut entries = Vec::new();
        for line in reader.lines() {
            let line = line.map_err(WalError::Io)?;
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            if let Ok(entry) = serde_json::from_str::<WalEntry>(trimmed) {
                entries.push(entry);
            }
        }
        Ok(entries)
    }

    /// Return the last (seq, hash) without materialising all payloads.
    pub fn last_seq_and_hash(&self) -> Result<(u64, String), WalError> {
        let entries = self.read_all()?;
        if let Some(last) = entries.last() {
            Ok((last.seq, last.hash.clone()))
        } else {
            Ok((0, String::new()))
        }
    }

    /// Verify the SHA-256 hash chain.
    pub fn verify_chain(&self) -> Result<bool, WalError> {
        let entries = self.read_all()?;
        let mut prev_hash = String::new();
        for entry in &entries {
            if entry.prev_hash != prev_hash {
                return Ok(false);
            }
            let expected = WalEntry::compute_hash(
                entry.seq,
                &entry.ts,
                &entry.op,
                &entry.record_id,
                &entry.record,
                &entry.prev_hash,
                entry.recursion_depth,
            );
            if entry.hash != expected {
                return Ok(false);
            }
            prev_hash = entry.hash.clone();
        }
        Ok(true)
    }
}

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------

#[derive(Debug, thiserror::Error)]
pub enum WalError {
    #[error("IO error: {0}")]
    Io(std::io::Error),
    #[error("Serialisation error: {0}")]
    Serialize(serde_json::Error),
    #[error("WAL not found: {0}")]
    NotFound(String),
}

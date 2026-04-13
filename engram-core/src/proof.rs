// engram-core/src/proof.rs
//
// Storage Proof — Challenge / Response protocol
//
// Single-CID flow:
//   1. Validator calls `generate_challenge(cid)` → Challenge { nonce, cid, expires_at }
//   2. Validator sends Challenge to miner
//   3. Miner calls `generate_response(challenge, embedding)` → ProofResponse
//   4. Validator calls `verify_response(challenge, response, embedding)` → bool
//
// Batch flow (preferred for audit sweeps):
//   1. Validator calls `generate_batch_challenge(cids)` → BatchChallenge
//   2. Miner calls `generate_batch_response(batch, embeddings)` → BatchProofResponse
//   3. Validator calls `verify_batch_response(batch, response, embeddings)` → Vec<bool>
//
// The single-CID proof binds: nonce + sha256(embedding_bytes)
// The batch proof binds:      nonce + cid_index + sha256(embedding_bytes)
//   (the index prevents a miner from shuffling valid proofs across positions)
//
// Both use HMAC-SHA256 with constant-time verification to prevent timing oracles.

use hmac::{Hmac, Mac};
use rand::RngCore;
use sha2::{Digest, Sha256};
use std::time::{SystemTime, UNIX_EPOCH};

type HmacSha256 = Hmac<Sha256>;

// ── Types ─────────────────────────────────────────────────────────────────────

#[derive(Debug, Clone)]
pub struct Challenge {
    pub nonce: [u8; 32],
    pub cid: String,
    pub issued_at: u64,   // unix seconds
    pub expires_at: u64,  // unix seconds
}

#[derive(Debug, Clone)]
pub struct ProofResponse {
    pub cid: String,
    pub nonce_hex: String,
    pub embedding_hash: String,  // sha256(embedding_bytes)
    pub proof: String,           // hmac-sha256(nonce || embedding_hash)
}

/// A single challenge for multiple CIDs sharing one nonce.
/// Saves round trips for audit sweeps that need to check dozens of CIDs at once.
#[derive(Debug, Clone)]
pub struct BatchChallenge {
    pub nonce: [u8; 32],      // one nonce covers the whole batch
    pub cids: Vec<String>,
    pub issued_at: u64,
    pub expires_at: u64,
}

/// One miner's response entry for a single CID within a batch.
#[derive(Debug, Clone)]
pub struct BatchProofEntry {
    pub cid: String,
    pub embedding_hash: String,
    pub proof: String,  // hmac-sha256(nonce || cid_index_le4 || embedding_hash)
}

#[derive(Debug, Clone)]
pub struct BatchProofResponse {
    pub nonce_hex: String,
    pub entries: Vec<BatchProofEntry>,
}

// ── Validator Side — single CID ───────────────────────────────────────────────

/// Generate a challenge for a given CID. The validator sends this to the miner.
pub fn generate_challenge(cid: &str, timeout_secs: u64) -> Challenge {
    let mut nonce = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut nonce);

    let now = unix_now();
    Challenge {
        nonce,
        cid: cid.to_string(),
        issued_at: now,
        expires_at: now + timeout_secs,
    }
}

/// Verify a miner's proof response.
///
/// All comparisons are constant-time to prevent timing oracles.
pub fn verify_response(
    challenge: &Challenge,
    response: &ProofResponse,
    embedding: &[f32],
) -> bool {
    // 1. CID must match
    if challenge.cid != response.cid {
        return false;
    }

    // 2. Not expired
    if unix_now() > challenge.expires_at {
        return false;
    }

    // 3. Nonce must match
    if response.nonce_hex != hex::encode(challenge.nonce) {
        return false;
    }

    // 4. Embedding hash — compute and compare constant-time
    let expected_emb_hash = hash_embedding(embedding);
    if !constant_time_eq_str(&expected_emb_hash, &response.embedding_hash) {
        return false;
    }

    // 5. HMAC proof — use mac.verify_slice() for guaranteed constant-time check
    verify_proof_ct(&challenge.nonce, &response.embedding_hash, &response.proof)
}

// ── Miner Side — single CID ───────────────────────────────────────────────────

/// Generate a proof response for a challenge, given the stored embedding.
pub fn generate_response(challenge: &Challenge, embedding: &[f32]) -> ProofResponse {
    let embedding_hash = hash_embedding(embedding);
    let proof = compute_proof(&challenge.nonce, &embedding_hash);

    ProofResponse {
        cid: challenge.cid.clone(),
        nonce_hex: hex::encode(challenge.nonce),
        embedding_hash,
        proof,
    }
}

// ── Validator Side — batch CIDs ───────────────────────────────────────────────

/// Generate a batch challenge covering multiple CIDs in one round trip.
pub fn generate_batch_challenge(cids: &[&str], timeout_secs: u64) -> BatchChallenge {
    let mut nonce = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut nonce);
    let now = unix_now();
    BatchChallenge {
        nonce,
        cids: cids.iter().map(|s| s.to_string()).collect(),
        issued_at: now,
        expires_at: now + timeout_secs,
    }
}

/// Verify a miner's batch response.
///
/// Returns one bool per CID in the original batch order.
/// Expired challenges fail all entries. Mismatched nonce fails all entries.
/// Individual CID failures are recorded per-entry so the validator can
/// slash/penalise at per-CID granularity without discarding the whole batch.
pub fn verify_batch_response(
    batch: &BatchChallenge,
    response: &BatchProofResponse,
    embeddings: &[Vec<f32>],
) -> Vec<bool> {
    let n = batch.cids.len();

    // Whole-batch guards — these are not per-entry
    if unix_now() > batch.expires_at {
        return vec![false; n];
    }
    if response.nonce_hex != hex::encode(batch.nonce) {
        return vec![false; n];
    }

    batch
        .cids
        .iter()
        .zip(embeddings.iter())
        .enumerate()
        .map(|(idx, (cid, emb))| {
            let entry = match response.entries.get(idx) {
                Some(e) => e,
                None => return false,
            };

            // CID at position must match what was challenged
            if entry.cid != *cid {
                return false;
            }

            // Embedding hash — constant-time
            let expected_hash = hash_embedding(emb);
            if !constant_time_eq_str(&expected_hash, &entry.embedding_hash) {
                return false;
            }

            // HMAC proof — constant-time, index-bound to prevent position shuffling
            verify_batch_proof_ct(&batch.nonce, idx as u32, &entry.embedding_hash, &entry.proof)
        })
        .collect()
}

// ── Miner Side — batch CIDs ───────────────────────────────────────────────────

/// Generate proof responses for all CIDs in a batch challenge.
pub fn generate_batch_response(
    batch: &BatchChallenge,
    embeddings: &[Vec<f32>],
) -> BatchProofResponse {
    let entries = batch
        .cids
        .iter()
        .zip(embeddings.iter())
        .enumerate()
        .map(|(idx, (cid, emb))| {
            let embedding_hash = hash_embedding(emb);
            let proof = compute_batch_proof(&batch.nonce, idx as u32, &embedding_hash);
            BatchProofEntry {
                cid: cid.clone(),
                embedding_hash,
                proof,
            }
        })
        .collect();

    BatchProofResponse {
        nonce_hex: hex::encode(batch.nonce),
        entries,
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

pub(crate) fn hash_embedding(embedding: &[f32]) -> String {
    let mut hasher = Sha256::new();

    #[cfg(target_endian = "little")]
    {
        // Safety: f32 and u8 have the same alignment requirements on LE systems;
        // we are only reinterpreting the memory layout, not doing arithmetic.
        let ptr = embedding.as_ptr() as *const u8;
        let len = embedding.len() * 4;
        let byte_slice = unsafe { std::slice::from_raw_parts(ptr, len) };
        hasher.update(byte_slice);
    }
    #[cfg(not(target_endian = "little"))]
    {
        for &f in embedding {
            hasher.update(&f.to_le_bytes());
        }
    }

    hex::encode(hasher.finalize())
}

/// Constant-time string equality.
/// Both strings must be the same byte length for this to be strictly CT; if
/// they differ in length we return false immediately (which leaks length, but
/// both sides derive the hash with the same algorithm so length is public).
fn constant_time_eq_str(a: &str, b: &str) -> bool {
    if a.len() != b.len() {
        return false;
    }
    // XOR-fold all bytes; any difference produces a non-zero accumulator.
    let diff = a
        .as_bytes()
        .iter()
        .zip(b.as_bytes().iter())
        .fold(0u8, |acc, (x, y)| acc | (x ^ y));
    diff == 0
}

/// Single-CID HMAC proof generation.
fn compute_proof(nonce: &[u8; 32], embedding_hash: &str) -> String {
    // TODO(production): replace nonce-as-key with a shared subnet secret or
    // the validator's hotkey so proofs cannot be forged even with nonce knowledge.
    let mut mac = HmacSha256::new_from_slice(nonce).expect("HMAC accepts any key length");
    mac.update(embedding_hash.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

/// Single-CID constant-time HMAC verification.
/// Uses `Mac::verify_slice` which is guaranteed constant-time by the hmac crate.
fn verify_proof_ct(nonce: &[u8; 32], embedding_hash: &str, proof_hex: &str) -> bool {
    let proof_bytes = match hex::decode(proof_hex) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let mut mac = HmacSha256::new_from_slice(nonce).expect("HMAC accepts any key length");
    mac.update(embedding_hash.as_bytes());
    mac.verify_slice(&proof_bytes).is_ok()
}

/// Batch HMAC proof: binds nonce + position index + embedding_hash.
/// The index prevents a miner from shuffling valid proofs between CID slots.
fn compute_batch_proof(nonce: &[u8; 32], cid_index: u32, embedding_hash: &str) -> String {
    let mut mac = HmacSha256::new_from_slice(nonce).expect("HMAC accepts any key length");
    mac.update(&cid_index.to_le_bytes());
    mac.update(embedding_hash.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

/// Batch HMAC constant-time verification.
fn verify_batch_proof_ct(
    nonce: &[u8; 32],
    cid_index: u32,
    embedding_hash: &str,
    proof_hex: &str,
) -> bool {
    let proof_bytes = match hex::decode(proof_hex) {
        Ok(b) => b,
        Err(_) => return false,
    };
    let mut mac = HmacSha256::new_from_slice(nonce).expect("HMAC accepts any key length");
    mac.update(&cid_index.to_le_bytes());
    mac.update(embedding_hash.as_bytes());
    mac.verify_slice(&proof_bytes).is_ok()
}

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock is before Unix epoch")
        .as_secs()
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_embedding() -> Vec<f32> {
        vec![0.1, 0.2, 0.3, 0.4, 0.5]
    }

    // ── Single-CID tests ──────────────────────────────────────────────────────

    #[test]
    fn valid_proof_verifies() {
        let emb = dummy_embedding();
        let challenge = generate_challenge("v1::abc123", 60);
        let response = generate_response(&challenge, &emb);
        assert!(verify_response(&challenge, &response, &emb));
    }

    #[test]
    fn wrong_embedding_fails() {
        let emb = dummy_embedding();
        let wrong_emb = vec![9.9f32; 5];
        let challenge = generate_challenge("v1::abc123", 60);
        let response = generate_response(&challenge, &emb);
        assert!(!verify_response(&challenge, &response, &wrong_emb));
    }

    #[test]
    fn wrong_cid_fails() {
        let emb = dummy_embedding();
        let challenge = generate_challenge("v1::abc123", 60);
        let mut response = generate_response(&challenge, &emb);
        response.cid = "v1::wrong".to_string();
        assert!(!verify_response(&challenge, &response, &emb));
    }

    #[test]
    fn tampered_proof_fails() {
        let emb = dummy_embedding();
        let challenge = generate_challenge("v1::abc123", 60);
        let mut response = generate_response(&challenge, &emb);
        // flip one hex char in the proof
        let mut chars: Vec<char> = response.proof.chars().collect();
        chars[0] = if chars[0] == 'a' { 'b' } else { 'a' };
        response.proof = chars.into_iter().collect();
        assert!(!verify_response(&challenge, &response, &emb));
    }

    // ── Batch tests ───────────────────────────────────────────────────────────

    #[test]
    fn batch_all_valid() {
        let cids = vec!["v1::aaa", "v1::bbb", "v1::ccc"];
        let embeddings: Vec<Vec<f32>> = vec![
            vec![0.1, 0.2],
            vec![0.3, 0.4],
            vec![0.5, 0.6],
        ];
        let batch = generate_batch_challenge(&cids, 60);
        let response = generate_batch_response(&batch, &embeddings);
        let results = verify_batch_response(&batch, &response, &embeddings);
        assert_eq!(results, vec![true, true, true]);
    }

    #[test]
    fn batch_one_wrong_embedding() {
        let cids = vec!["v1::aaa", "v1::bbb"];
        let embeddings: Vec<Vec<f32>> = vec![vec![0.1, 0.2], vec![0.3, 0.4]];
        let batch = generate_batch_challenge(&cids, 60);
        let response = generate_batch_response(&batch, &embeddings);

        // Verify with wrong embedding for second slot
        let wrong_embeddings = vec![vec![0.1f32, 0.2], vec![9.9f32, 9.9]];
        let results = verify_batch_response(&batch, &response, &wrong_embeddings);
        assert_eq!(results, vec![true, false]);
    }

    #[test]
    fn batch_proof_not_shuffleable() {
        // A miner cannot swap valid proofs between slots
        let cids = vec!["v1::aaa", "v1::bbb"];
        let embeddings: Vec<Vec<f32>> = vec![vec![0.1, 0.2], vec![0.3, 0.4]];
        let batch = generate_batch_challenge(&cids, 60);
        let mut response = generate_batch_response(&batch, &embeddings);

        // Swap the two entries
        response.entries.swap(0, 1);
        let results = verify_batch_response(&batch, &response, &embeddings);
        // Both must fail: CID in entry doesn't match expected position
        assert_eq!(results, vec![false, false]);
    }

    #[test]
    fn batch_expired_fails_all() {
        let cids = vec!["v1::aaa"];
        let embeddings = vec![vec![0.1f32]];
        let mut batch = generate_batch_challenge(&cids, 0);
        batch.expires_at = 0; // already expired
        let response = generate_batch_response(&batch, &embeddings);
        let results = verify_batch_response(&batch, &response, &embeddings);
        assert_eq!(results, vec![false]);
    }
}

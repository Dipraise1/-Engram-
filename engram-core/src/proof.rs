// engram-core/src/proof.rs
//
// Storage Proof — Challenge / Response protocol
//
// Flow:
//   1. Validator calls `generate_challenge(cid)` → Challenge { nonce, cid, expires_at }
//   2. Validator sends Challenge to miner
//   3. Miner calls `generate_response(challenge, embedding)` → ProofResponse
//   4. Validator calls `verify_response(challenge, response, embedding)` → bool
//
// The proof binds: nonce + cid + sha256(embedding_bytes)
// This proves the miner has the actual vector, not just the CID.

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
    pub proof: String,           // hmac(nonce || embedding_hash)
}

// ── Validator Side ─────────────────────────────────────────────────────────────

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
/// # Arguments
/// * `challenge`  - the original challenge issued by the validator
/// * `response`   - the miner's response
/// * `embedding`  - the expected embedding (from ground truth or stored copy)
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
    let expected_nonce_hex = hex::encode(challenge.nonce);
    if response.nonce_hex != expected_nonce_hex {
        return false;
    }

    // 4. Embedding hash must match actual embedding
    let expected_emb_hash = hash_embedding(embedding);
    if response.embedding_hash != expected_emb_hash {
        return false;
    }

    // 5. HMAC proof must be valid
    let expected_proof = compute_proof(&challenge.nonce, &response.embedding_hash);
    response.proof == expected_proof
}

// ── Miner Side ────────────────────────────────────────────────────────────────

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

// ── Helpers ───────────────────────────────────────────────────────────────────

fn hash_embedding(embedding: &[f32]) -> String {
    let mut bytes = Vec::with_capacity(embedding.len() * 4);
    for &f in embedding {
        bytes.extend_from_slice(&f.to_le_bytes());
    }
    let digest = Sha256::digest(&bytes);
    hex::encode(digest)
}

fn compute_proof(nonce: &[u8; 32], embedding_hash: &str) -> String {
    // HMAC key = nonce itself; message = embedding_hash bytes
    // In production the key would be a shared subnet secret or validator hotkey.
    let mut mac = HmacSha256::new_from_slice(nonce).expect("HMAC accepts any key length");
    mac.update(embedding_hash.as_bytes());
    hex::encode(mac.finalize().into_bytes())
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
}

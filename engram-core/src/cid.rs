// engram-core/src/cid.rs
//
// CID generation for embedding vectors.
// Format: "v1::<sha256hex>"
//   sha256 input = embedding_bytes (f32 LE) ++ canonical_metadata_json_bytes
//
// This is the single source of truth for CID generation.
// The Python layer calls into this via PyO3 — never reimplement the hash in Python.

use sha2::{Digest, Sha256};
use std::collections::BTreeMap;

/// Generate a CID from raw f32 embedding bytes and a JSON-serializable metadata map.
///
/// # Arguments
/// * `embedding` - f32 vector (will be serialized as little-endian bytes)
/// * `metadata`  - key-value metadata included in the hash (sorted for determinism)
/// * `model_version` - e.g. "v1"; injected into metadata before hashing
pub fn generate_cid(
    embedding: &[f32],
    metadata: &BTreeMap<String, String>,
    model_version: &str,
) -> String {
    let mut canonical = metadata.clone();
    canonical.insert("model_version".to_string(), model_version.to_string());

    let meta_json = serde_json::to_string(&canonical)
        .expect("metadata serialization is infallible for BTreeMap<String,String>");
    let meta_bytes = meta_json.as_bytes();

    let mut hasher = Sha256::new();
    
    #[cfg(target_endian = "little")]
    {
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

    hasher.update(meta_bytes);
    let digest = hasher.finalize();

    format!("v1::{}", hex::encode(digest))
}

/// Verify a CID against an embedding + metadata.
pub fn verify_cid(
    cid: &str,
    embedding: &[f32],
    metadata: &BTreeMap<String, String>,
    model_version: &str,
) -> bool {
    let expected = generate_cid(embedding, metadata, model_version);
    cid == expected
}

/// Parse a CID string into (version, sha256_hex).
pub fn parse_cid(cid: &str) -> Result<(&str, &str), String> {
    let parts: Vec<&str> = cid.splitn(2, "::").collect();
    if parts.len() != 2 {
        return Err(format!("Invalid CID format: {cid}"));
    }
    let (version, digest) = (parts[0], parts[1]);
    if digest.len() != 64 {
        return Err(format!(
            "CID hash must be 64 hex chars, got {}: {cid}",
            digest.len()
        ));
    }
    Ok((version, digest))
}

// ── Helpers ───────────────────────────────────────────────────────────────────

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_meta() -> BTreeMap<String, String> {
        BTreeMap::new()
    }

    #[test]
    fn same_input_same_cid() {
        let emb = vec![0.1f32, 0.2, 0.3];
        let c1 = generate_cid(&emb, &empty_meta(), "v1");
        let c2 = generate_cid(&emb, &empty_meta(), "v1");
        assert_eq!(c1, c2);
    }

    #[test]
    fn different_input_different_cid() {
        let emb1 = vec![0.1f32, 0.2, 0.3];
        let emb2 = vec![0.1f32, 0.2, 0.4];
        assert_ne!(
            generate_cid(&emb1, &empty_meta(), "v1"),
            generate_cid(&emb2, &empty_meta(), "v1")
        );
    }

    #[test]
    fn different_model_version_different_cid() {
        let emb = vec![0.1f32, 0.2, 0.3];
        assert_ne!(
            generate_cid(&emb, &empty_meta(), "v1"),
            generate_cid(&emb, &empty_meta(), "v2")
        );
    }

    #[test]
    fn cid_starts_with_version() {
        let emb = vec![0.5f32];
        let cid = generate_cid(&emb, &empty_meta(), "v1");
        assert!(cid.starts_with("v1::"));
    }

    #[test]
    fn verify_roundtrip() {
        let emb = vec![0.1f32, 0.9, 0.5];
        let cid = generate_cid(&emb, &empty_meta(), "v1");
        assert!(verify_cid(&cid, &emb, &empty_meta(), "v1"));
        assert!(!verify_cid(&cid, &[0.0f32], &empty_meta(), "v1"));
    }

    #[test]
    fn parse_valid_cid() {
        let emb = vec![1.0f32];
        let cid = generate_cid(&emb, &empty_meta(), "v1");
        let (ver, digest) = parse_cid(&cid).unwrap();
        assert_eq!(ver, "v1");
        assert_eq!(digest.len(), 64);
    }
}

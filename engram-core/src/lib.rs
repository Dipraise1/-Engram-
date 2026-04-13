// engram-core/src/lib.rs
//
// PyO3 bindings — exposes the Rust CID and proof modules to Python.
//
// Single-CID usage:
//   import engram_core
//   cid = engram_core.generate_cid([0.1, 0.2, 0.3], {}, "v1")
//   valid = engram_core.verify_cid(cid, [0.1, 0.2, 0.3], {}, "v1")
//
//   challenge = engram_core.generate_challenge("v1::abc...", 30)
//   response  = engram_core.generate_response(challenge, [0.1, 0.2, 0.3])
//   ok        = engram_core.verify_response(challenge, response, [0.1, 0.2, 0.3])
//
// Batch usage (preferred for audit sweeps — one nonce, N CIDs, one round trip):
//   batch    = engram_core.generate_batch_challenge(["v1::aaa", "v1::bbb"], 30)
//   response = engram_core.generate_batch_response(batch, [[0.1, 0.2], [0.3, 0.4]])
//   results  = engram_core.verify_batch_response(batch, response, [[0.1, 0.2], [0.3, 0.4]])
//   # results: list[bool], one per CID

use pyo3::prelude::*;
use std::collections::BTreeMap;

mod cid;
mod proof;

// ── CID bindings ──────────────────────────────────────────────────────────────

#[pyfunction]
#[pyo3(signature = (embedding, metadata=None, model_version="v1"))]
fn generate_cid(
    embedding: Vec<f32>,
    metadata: Option<std::collections::HashMap<String, String>>,
    model_version: &str,
) -> PyResult<String> {
    let meta: BTreeMap<String, String> = metadata
        .unwrap_or_default()
        .into_iter()
        .collect();
    Ok(cid::generate_cid(&embedding, &meta, model_version))
}

#[pyfunction]
#[pyo3(signature = (cid_str, embedding, metadata=None, model_version="v1"))]
fn verify_cid(
    cid_str: &str,
    embedding: Vec<f32>,
    metadata: Option<std::collections::HashMap<String, String>>,
    model_version: &str,
) -> PyResult<bool> {
    let meta: BTreeMap<String, String> = metadata
        .unwrap_or_default()
        .into_iter()
        .collect();
    Ok(cid::verify_cid(cid_str, &embedding, &meta, model_version))
}

#[pyfunction]
fn parse_cid(cid_str: &str) -> PyResult<(String, String)> {
    cid::parse_cid(cid_str)
        .map(|(v, d)| (v.to_string(), d.to_string()))
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e))
}

// ── Single-CID Challenge / Proof bindings ─────────────────────────────────────

/// Python-visible Challenge object
#[pyclass]
#[derive(Clone)]
struct Challenge {
    inner: proof::Challenge,
}

#[pymethods]
impl Challenge {
    #[getter]
    fn cid(&self) -> &str { &self.inner.cid }
    #[getter]
    fn nonce_hex(&self) -> String { hex::encode(self.inner.nonce) }
    #[getter]
    fn issued_at(&self) -> u64 { self.inner.issued_at }
    #[getter]
    fn expires_at(&self) -> u64 { self.inner.expires_at }
}

/// Python-visible ProofResponse object
#[pyclass]
#[derive(Clone)]
struct ProofResponse {
    inner: proof::ProofResponse,
}

#[pymethods]
impl ProofResponse {
    #[getter]
    fn cid(&self) -> &str { &self.inner.cid }
    #[getter]
    fn nonce_hex(&self) -> &str { &self.inner.nonce_hex }
    #[getter]
    fn embedding_hash(&self) -> &str { &self.inner.embedding_hash }
    #[getter]
    fn proof(&self) -> &str { &self.inner.proof }
}

#[pyfunction]
#[pyo3(signature = (cid_str, timeout_secs=30))]
fn generate_challenge(cid_str: &str, timeout_secs: u64) -> Challenge {
    Challenge {
        inner: proof::generate_challenge(cid_str, timeout_secs),
    }
}

#[pyfunction]
fn generate_response(challenge: &Challenge, embedding: Vec<f32>) -> ProofResponse {
    ProofResponse {
        inner: proof::generate_response(&challenge.inner, &embedding),
    }
}

#[pyfunction]
fn verify_response(
    challenge: &Challenge,
    response: &ProofResponse,
    embedding: Vec<f32>,
) -> bool {
    proof::verify_response(&challenge.inner, &response.inner, &embedding)
}

// ── Batch Challenge / Proof bindings ─────────────────────────────────────────

/// Python-visible BatchChallenge: one nonce covering N CIDs.
#[pyclass]
#[derive(Clone)]
struct BatchChallenge {
    inner: proof::BatchChallenge,
}

#[pymethods]
impl BatchChallenge {
    /// List of CIDs this challenge covers, in order.
    #[getter]
    fn cids(&self) -> Vec<String> { self.inner.cids.clone() }
    #[getter]
    fn nonce_hex(&self) -> String { hex::encode(self.inner.nonce) }
    #[getter]
    fn issued_at(&self) -> u64 { self.inner.issued_at }
    #[getter]
    fn expires_at(&self) -> u64 { self.inner.expires_at }
}

/// Python-visible per-entry proof within a batch response.
#[pyclass]
#[derive(Clone)]
struct BatchProofEntry {
    inner: proof::BatchProofEntry,
}

#[pymethods]
impl BatchProofEntry {
    #[getter]
    fn cid(&self) -> &str { &self.inner.cid }
    #[getter]
    fn embedding_hash(&self) -> &str { &self.inner.embedding_hash }
    #[getter]
    fn proof(&self) -> &str { &self.inner.proof }
}

/// Python-visible BatchProofResponse.
#[pyclass]
#[derive(Clone)]
struct BatchProofResponse {
    inner: proof::BatchProofResponse,
}

#[pymethods]
impl BatchProofResponse {
    #[getter]
    fn nonce_hex(&self) -> &str { &self.inner.nonce_hex }
    /// Per-CID proof entries, in the same order as the original BatchChallenge.
    #[getter]
    fn entries(&self) -> Vec<BatchProofEntry> {
        self.inner.entries.iter().map(|e| BatchProofEntry { inner: e.clone() }).collect()
    }
}

/// Generate a batch challenge covering multiple CIDs in one round trip.
///
/// Args:
///     cids:         list of CID strings to challenge
///     timeout_secs: how long the challenge is valid (default 30)
#[pyfunction]
#[pyo3(signature = (cids, timeout_secs=30))]
fn generate_batch_challenge(cids: Vec<String>, timeout_secs: u64) -> BatchChallenge {
    let cid_refs: Vec<&str> = cids.iter().map(String::as_str).collect();
    BatchChallenge {
        inner: proof::generate_batch_challenge(&cid_refs, timeout_secs),
    }
}

/// Miner side: respond to a batch challenge.
///
/// Args:
///     batch:      the BatchChallenge issued by the validator
///     embeddings: list of embedding vectors, one per CID in batch.cids order
#[pyfunction]
fn generate_batch_response(
    batch: &BatchChallenge,
    embeddings: Vec<Vec<f32>>,
) -> BatchProofResponse {
    BatchProofResponse {
        inner: proof::generate_batch_response(&batch.inner, &embeddings),
    }
}

/// Validator side: verify a miner's batch response.
///
/// Returns a list[bool] — one result per CID in the original batch order.
/// Expired challenges or nonce mismatches return all-False.
/// Individual failures are per-entry so you can penalise at CID granularity.
#[pyfunction]
fn verify_batch_response(
    batch: &BatchChallenge,
    response: &BatchProofResponse,
    embeddings: Vec<Vec<f32>>,
) -> Vec<bool> {
    proof::verify_batch_response(&batch.inner, &response.inner, &embeddings)
}

// ── Module ────────────────────────────────────────────────────────────────────

#[pymodule]
fn engram_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // CID
    m.add_function(wrap_pyfunction!(generate_cid, m)?)?;
    m.add_function(wrap_pyfunction!(verify_cid, m)?)?;
    m.add_function(wrap_pyfunction!(parse_cid, m)?)?;
    // Single-CID proofs
    m.add_class::<Challenge>()?;
    m.add_class::<ProofResponse>()?;
    m.add_function(wrap_pyfunction!(generate_challenge, m)?)?;
    m.add_function(wrap_pyfunction!(generate_response, m)?)?;
    m.add_function(wrap_pyfunction!(verify_response, m)?)?;
    // Batch proofs
    m.add_class::<BatchChallenge>()?;
    m.add_class::<BatchProofEntry>()?;
    m.add_class::<BatchProofResponse>()?;
    m.add_function(wrap_pyfunction!(generate_batch_challenge, m)?)?;
    m.add_function(wrap_pyfunction!(generate_batch_response, m)?)?;
    m.add_function(wrap_pyfunction!(verify_batch_response, m)?)?;
    Ok(())
}

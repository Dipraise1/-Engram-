// engram-core/src/lib.rs
//
// PyO3 bindings — exposes the Rust CID and proof modules to Python.
//
// Python usage:
//   import engram_core
//   cid = engram_core.generate_cid([0.1, 0.2, 0.3], {}, "v1")
//   valid = engram_core.verify_cid(cid, [0.1, 0.2, 0.3], {}, "v1")
//
//   challenge = engram_core.generate_challenge("v1::abc...", 30)
//   response  = engram_core.generate_response(challenge, [0.1, 0.2, 0.3])
//   ok        = engram_core.verify_response(challenge, response, [0.1, 0.2, 0.3])

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

// ── Challenge / Proof bindings ─────────────────────────────────────────────────

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

// ── Module ────────────────────────────────────────────────────────────────────

#[pymodule]
fn engram_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // CID
    m.add_function(wrap_pyfunction!(generate_cid, m)?)?;
    m.add_function(wrap_pyfunction!(verify_cid, m)?)?;
    m.add_function(wrap_pyfunction!(parse_cid, m)?)?;
    // Proofs
    m.add_class::<Challenge>()?;
    m.add_class::<ProofResponse>()?;
    m.add_function(wrap_pyfunction!(generate_challenge, m)?)?;
    m.add_function(wrap_pyfunction!(generate_response, m)?)?;
    m.add_function(wrap_pyfunction!(verify_response, m)?)?;
    Ok(())
}

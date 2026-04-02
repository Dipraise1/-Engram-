import pytest
import numpy as np
from unittest.mock import patch, MagicMock

import bittensor as bt

from engram.protocol import IngestSynapse, QuerySynapse, ChallengeSynapse
from engram.miner.store import FAISSStore, VectorRecord
from engram.validator.reward import RewardManager
import engram_core

@pytest.fixture
def store():
    return FAISSStore(dim=5)

@pytest.fixture
def mock_embed():
    with patch("engram.miner.embedder.Embedder.embed") as m:
        m.return_value = np.array([0.1, 0.2, 0.3, 0.4, 0.5], dtype=np.float32)
        yield m

def test_e2e_lifecycle(store, mock_embed):
    text = "Decentralized vector database subnet"
    
    miner_uid = 42
    recall_scores = {}
    proof_rates = {}
    latency_scores = {}
    
    # -------------------------------------------------------------
    # 1. INGEST
    # -------------------------------------------------------------
    ingest_syn = IngestSynapse(text=text, model_version="v1")
    
    # -> Miner Processing
    emb = mock_embed(ingest_syn.text)
    cid = engram_core.generate_cid(emb.tolist(), {}, "v1")
    store.upsert(VectorRecord(cid=cid, embedding=emb))
    ingest_syn.cid = cid
    
    # <- Validator Asserts
    assert ingest_syn.cid is not None
    assert store.count() == 1
    
    # -------------------------------------------------------------
    # 2. QUERY
    # -------------------------------------------------------------
    query_syn = QuerySynapse(query_vector=emb.tolist(), top_k=5)
    
    # -> Miner Processing
    q_vec = np.array(query_syn.query_vector, dtype=np.float32)
    results = store.search(q_vec, top_k=query_syn.top_k)
    query_syn.results = [{"cid": r.cid, "score": r.score, "metadata": r.metadata} for r in results]
    query_syn.latency_ms = 45.0
    
    # <- Validator Asserts
    returned_cids = [r["cid"] for r in query_syn.results]
    assert cid in returned_cids
    recall_scores[miner_uid] = 1.0  # Found it
    latency_scores[miner_uid] = query_syn.latency_ms
    
    # -------------------------------------------------------------
    # 3. CHALLENGE (Proof of Storage)
    # -------------------------------------------------------------
    challenge = engram_core.generate_challenge(cid, 60)
    chal_syn = ChallengeSynapse(
        cid=challenge.cid,
        nonce_hex=challenge.nonce_hex,
        expires_at=challenge.expires_at
    )
    
    # -> Miner Processing
    miner_record = store.get(chal_syn.cid)
    assert miner_record is not None
    miner_response = engram_core.generate_response(challenge, miner_record.embedding.tolist())
    chal_syn.embedding_hash = miner_response.embedding_hash
    chal_syn.proof = miner_response.proof
    
    # <- Validator Asserts
    is_valid_proof = engram_core.verify_response(challenge, miner_response, emb.tolist())
    assert is_valid_proof is True
    proof_rates[miner_uid] = 1.0
    
    # -------------------------------------------------------------
    # 4. REWARD / SCORING
    # -------------------------------------------------------------
    mock_subtensor = MagicMock()
    mock_subtensor.set_weights.return_value = True
    mock_wallet = MagicMock()
    mock_metagraph = MagicMock()
    mock_metagraph.uids = np.array([miner_uid])
    
    rm = RewardManager(mock_subtensor, mock_wallet, netuid=1)
    
    success = rm.set_weights(mock_metagraph, recall_scores, latency_scores, proof_rates)
    
    assert success is True
    assert miner_uid in rm.moving_averages
    assert rm.moving_averages[miner_uid] > 0.05

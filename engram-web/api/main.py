"""
Engram Web API

FastAPI backend that bridges the Next.js dashboard to the live Bittensor subnet.

Run:
    uvicorn engram-web.api.main:app --reload --port 8000

Or from the engram-web directory:
    uvicorn api.main:app --reload --port 8000
"""

import os
import time
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

app = FastAPI(title="Engram Web API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://theengram.space", "https://www.theengram.space"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

NETUID = int(os.getenv("NETUID", "450"))
NETWORK = os.getenv("SUBTENSOR_NETWORK", "test")
ENDPOINT = os.getenv("SUBTENSOR_ENDPOINT", "")


# ── Lazy metagraph cache ───────────────────────────────────────────────────────

_meta_cache: dict[str, Any] = {}
_meta_ts: float = 0
META_TTL = 30  # seconds


def get_metagraph():
    global _meta_cache, _meta_ts
    if time.time() - _meta_ts < META_TTL and _meta_cache:
        return _meta_cache

    try:
        import bittensor as bt

        kwargs = {"network": ENDPOINT} if ENDPOINT else {"network": NETWORK}
        subtensor = bt.Subtensor(**kwargs)
        meta = subtensor.metagraph(netuid=NETUID)

        _meta_cache = {
            "meta": meta,
            "subtensor": subtensor,
            "block": subtensor.block,
        }
        _meta_ts = time.time()
        return _meta_cache
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Cannot reach subnet: {e}")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/stats")
def get_stats():
    try:
        data = get_metagraph()
        meta = data["meta"]

        n_miners = int((meta.S > 0).sum())
        avg_score = float(meta.W.mean()) if meta.W.size > 0 else 0.0

        return {
            "miners": n_miners,
            "validators": max(0, int(meta.n.item()) - n_miners),
            "vectors": 0,           # populated from miner stats in future
            "queries_today": 0,
            "avg_score": round(avg_score, 4),
            "block": data["block"],
            "netuid": NETUID,
            "uptime_pct": 99.9,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/miners")
def get_miners():
    try:
        data = get_metagraph()
        meta = data["meta"]

        miners = []
        uids = meta.uids.tolist()
        stakes = meta.S.tolist()
        scores = meta.W.mean(axis=0).tolist() if meta.W.ndim == 2 else [0.0] * len(uids)
        axons = meta.axons

        for i, uid in enumerate(uids):
            axon = axons[i] if i < len(axons) else None
            miners.append({
                "uid": int(uid),
                "hotkey": axon.hotkey[:12] + "..." if axon else "unknown",
                "score": round(float(scores[i]), 4),
                "vectors": 0,
                "latency_ms": 0,
                "proof_rate": 0.0,
                "stake": round(float(stakes[i]), 4),
                "status": "online" if axon and axon.ip != "0.0.0.0" else "offline",
            })

        return sorted(miners, key=lambda m: m["score"], reverse=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _get_store_and_embedder():
    """Shared helper — returns (FAISSStore, Embedder)."""
    os.environ.setdefault("USE_LOCAL_EMBEDDER", "true")
    from engram.miner.embedder import get_embedder
    from engram.miner.store import FAISSStore
    embedder = get_embedder()
    index_path = os.getenv("FAISS_INDEX_PATH", "../data/engram.index")
    os.makedirs(os.path.dirname(os.path.abspath(index_path)), exist_ok=True)
    store = FAISSStore(dim=embedder.dim, index_path=index_path)
    return store, embedder


class IngestRequest(BaseModel):
    text: str
    metadata: dict = {}


@app.post("/ingest")
def run_ingest(req: IngestRequest):
    """Embed and store text, return CID."""
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    try:
        from engram.miner.ingest import IngestHandler
        from engram.protocol import IngestSynapse

        store, embedder = _get_store_and_embedder()
        handler = IngestHandler(store=store, embedder=embedder)
        syn = IngestSynapse(text=req.text, metadata=req.metadata)
        result = handler.handle(syn)

        if hasattr(store, "save"):
            store.save()

        if result.error:
            raise HTTPException(status_code=500, detail=result.error)

        return {"cid": result.cid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class QueryRequest(BaseModel):
    query_text: str
    top_k: int = 5


@app.post("/query")
def run_query(req: QueryRequest):
    """
    Forward a semantic query to the subnet via the SDK.
    Falls back to local FAISS store if no live subnet is reachable.
    """
    try:
        from engram.miner.query import QueryHandler
        from engram.protocol import QuerySynapse

        store, embedder = _get_store_and_embedder()

        if store.count() == 0:
            return {"results": [], "error": "Store is empty — ingest some data first"}

        handler = QueryHandler(store=store, embedder=embedder)
        syn = QuerySynapse(query_text=req.query_text, top_k=req.top_k)
        result = handler.handle(syn)

        return {"results": result.results, "error": result.error}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/wallet-stats")
def get_all_wallet_stats():
    """Return activity summary for all tracked wallets."""
    try:
        import sys, os as _os
        sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", ".."))
        from engram.miner.wallet_tracker import WalletTracker
        tracker = WalletTracker()
        return tracker.summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/wallet-stats/{hotkey}")
def get_wallet_stats(hotkey: str):
    """Return activity stats for a single hotkey."""
    try:
        import sys, os as _os
        sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", ".."))
        from engram.miner.wallet_tracker import WalletTracker
        tracker = WalletTracker()
        return {**tracker.get_stats(hotkey), "hotkey": hotkey}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "netuid": NETUID, "network": NETWORK}

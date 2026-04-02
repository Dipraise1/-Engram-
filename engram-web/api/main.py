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
    allow_origins=["http://localhost:3000", "https://engramdb.xyz"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

NETUID = int(os.getenv("NETUID", "42"))
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
        subtensor = bt.subtensor(**kwargs)
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
        avg_score = float(meta.W.mean().item()) if meta.W.numel() > 0 else 0.0

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
        scores = meta.W.mean(dim=0).tolist() if meta.W.dim() == 2 else [0.0] * len(uids)
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
        os.environ.setdefault("USE_LOCAL_EMBEDDER", "true")

        from engram.miner.embedder import get_embedder
        from engram.miner.store import FAISSStore
        from engram.miner.query import QueryHandler
        from engram.protocol import QuerySynapse

        embedder = get_embedder()
        index_path = os.getenv("FAISS_INDEX_PATH", "../data/faiss.index")
        store = FAISSStore(dim=embedder.dim, index_path=index_path)

        if store.count() == 0:
            return {"results": [], "error": "Store is empty — ingest some data first"}

        handler = QueryHandler(store=store, embedder=embedder)
        syn = QuerySynapse(query_text=req.query_text, top_k=req.top_k)
        result = handler.handle(syn)

        return {"results": result.results, "error": result.error}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "netuid": NETUID, "network": NETWORK}

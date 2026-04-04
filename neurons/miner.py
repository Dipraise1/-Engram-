"""
Engram — Miner Neuron

Serves a plain JSON HTTP API (aiohttp) so the validator's direct HTTP calls work.
Registers axon info on-chain via subtensor.serve_axon() for metagraph discovery.

Endpoints:
  POST /IngestSynapse   → store embedding, return CID
  POST /QuerySynapse    → ANN search, return top-K results
  POST /ChallengeSynapse → storage proof response (uses validator's nonce)
  GET  /health          → liveness probe
"""

import asyncio
import hashlib
import hmac as _hmac
import os
import struct
import time

import bittensor as bt
from aiohttp import web
from dotenv import load_dotenv
from loguru import logger

from engram.config import SUBNET_VERSION
from engram.miner.embedder import get_embedder
from engram.miner.ingest import IngestHandler
from engram.miner.metrics import METRICS, generate_latest
from engram.miner.query import QueryHandler
from engram.miner.rate_limiter import RateLimiter
from engram.miner.wallet_tracker import WalletTracker
from engram.miner.store import build_store
from engram.protocol import IngestSynapse, QuerySynapse
from engram.storage.dht import DHTRouter, Peer
from engram.storage.replication import ReplicationManager
from engram.utils.logging import setup_logging

load_dotenv()
setup_logging(os.getenv("LOG_LEVEL", "INFO"))


# ── Storage proof helpers ─────────────────────────────────────────────────────
# Mirrors Rust proof.rs logic exactly: SHA-256 over little-endian f32 bytes,
# then HMAC-SHA256 with nonce as key and embedding_hash hex as message.

def _hash_embedding(embedding: list[float]) -> str:
    emb_bytes = struct.pack(f"<{len(embedding)}f", *embedding)
    return hashlib.sha256(emb_bytes).hexdigest()


def _compute_proof(nonce: bytes, embedding_hash: str) -> str:
    mac = _hmac.new(nonce, embedding_hash.encode(), hashlib.sha256)
    return mac.hexdigest()


def _proof_response(nonce_hex: str, embedding: list[float]) -> tuple[str, str]:
    nonce = bytes.fromhex(nonce_hex)
    embedding_hash = _hash_embedding(embedding)
    proof = _compute_proof(nonce, embedding_hash)
    return embedding_hash, proof


# ── Main ──────────────────────────────────────────────────────────────────────

async def run() -> None:
    wallet_name   = os.getenv("WALLET_NAME", "default")
    wallet_hotkey = os.getenv("WALLET_HOTKEY", "default")
    network       = os.getenv("SUBTENSOR_ENDPOINT") or os.getenv("SUBTENSOR_NETWORK", "test")
    netuid        = int(os.getenv("NETUID", "99"))
    port          = int(os.getenv("MINER_PORT", "8091"))
    backend       = os.getenv("VECTOR_STORE_BACKEND", "faiss")
    external_ip   = os.getenv("EXTERNAL_IP", "127.0.0.1")

    logger.info(f"Engram Miner v{SUBNET_VERSION} | network={network} | netuid={netuid}")

    # ── Bittensor setup ───────────────────────────────────────────────────────
    wallet     = bt.Wallet(name=wallet_name, hotkey=wallet_hotkey)
    subtensor  = bt.Subtensor(network=network)
    metagraph  = subtensor.metagraph(netuid=netuid)

    logger.info(f"Wallet: {wallet.hotkey.ss58_address}")

    # ── Core components ───────────────────────────────────────────────────────
    store          = build_store(backend)
    embedder       = get_embedder()
    ingest_handler = IngestHandler(store=store, embedder=embedder,
                                   subtensor=subtensor, netuid=netuid)
    query_handler  = QueryHandler(store=store, embedder=embedder)
    rate_limiter    = RateLimiter()
    wallet_tracker  = WalletTracker()

    logger.info(f"Vector store: {backend} | {store.count()} vectors loaded")

    # ── DHT + Replication ─────────────────────────────────────────────────────
    our_uid = next(
        (int(uid) for uid, axon in zip(metagraph.uids.tolist(), metagraph.axons)
         if axon.hotkey == wallet.hotkey.ss58_address),
        0,
    )
    local_peer = Peer(uid=our_uid, hotkey=wallet.hotkey.ss58_address,
                      ip=external_ip, port=port)
    router         = DHTRouter(local_peer=local_peer)
    router.sync_from_metagraph(axons=metagraph.axons, uids=metagraph.uids.tolist())
    replication_mgr = ReplicationManager(router=router)

    logger.info(f"DHT ready | peers={router.peer_count()} | uid={our_uid}")

    # ── Registration check ────────────────────────────────────────────────────
    if not subtensor.is_hotkey_registered(netuid=netuid, hotkey_ss58=wallet.hotkey.ss58_address):
        logger.warning("Hotkey not registered — run:")
        logger.warning(f"  btcli subnet register --netuid {netuid} --wallet.name {wallet_name}")

    # ── HTTP handlers ─────────────────────────────────────────────────────────

    async def handle_ingest(req: web.Request) -> web.Response:
        import time as _time
        t0 = _time.perf_counter()
        try:
            body          = await req.json()
            caller_hotkey = body.get("hotkey")

            if caller_hotkey:
                try:
                    rate_limiter.check(caller_hotkey)
                except ValueError as exc:
                    METRICS.ingest_total.labels(status="rate_limited").inc()
                    return web.json_response({"error": str(exc)}, status=429)

            synapse  = IngestSynapse(
                text          = body.get("text"),
                raw_embedding = body.get("raw_embedding"),
                metadata      = body.get("metadata") or {},
            )
            result = ingest_handler.handle(synapse, caller_hotkey=caller_hotkey)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            METRICS.ingest_duration.observe(elapsed_ms)

            if result.error:
                status = "low_stake" if "stake" in (result.error or "") else "error"
                METRICS.ingest_total.labels(status=status).inc()
            else:
                METRICS.ingest_total.labels(status="ok").inc()
                METRICS.vectors_stored.set(store.count())
                replication_mgr.register(result.cid)
                if caller_hotkey:
                    wallet_tracker.record_ingest(caller_hotkey, result.cid)
                if not router.should_store(result.cid):
                    logger.debug(f"DHT: not primary for {result.cid[:16]}… (stored anyway)")

            return web.json_response({"cid": result.cid, "error": result.error})
        except Exception as exc:
            METRICS.ingest_total.labels(status="error").inc()
            logger.error(f"Ingest error: {exc}")
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_query(req: web.Request) -> web.Response:
        import time as _time
        t0 = _time.perf_counter()
        try:
            body    = await req.json()
            caller_hotkey = body.get("hotkey")
            synapse = QuerySynapse(
                query_text   = body.get("query_text"),
                query_vector = body.get("query_vector"),
                top_k        = int(body.get("top_k", 10)),
            )
            result = query_handler.handle(synapse)
            elapsed_ms = (_time.perf_counter() - t0) * 1000
            METRICS.query_duration.observe(elapsed_ms)
            METRICS.query_total.labels(status="error" if result.error else "ok").inc()
            if caller_hotkey and not result.error:
                wallet_tracker.record_query(caller_hotkey)
            return web.json_response({
                "results"   : result.results or [],
                "latency_ms": result.latency_ms,
                "error"     : result.error,
            })
        except Exception as exc:
            METRICS.query_total.labels(status="error").inc()
            logger.error(f"Query error: {exc}")
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_challenge(req: web.Request) -> web.Response:
        try:
            body      = await req.json()
            cid       = body.get("cid", "")
            nonce_hex = body.get("nonce_hex", "")
            expires_at = int(body.get("expires_at", 0))

            if time.time() > expires_at:
                return web.json_response({"error": "challenge expired"}, status=400)

            record = store.get(cid)
            if record is None:
                return web.json_response({"error": f"CID not found: {cid}"}, status=404)

            embedding_hash, proof = _proof_response(nonce_hex, record.embedding.tolist())
            return web.json_response({"embedding_hash": embedding_hash, "proof": proof})

        except Exception as exc:
            logger.error(f"Challenge error: {exc}")
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_wallet_stats(req: web.Request) -> web.Response:
        hotkey = req.match_info.get("hotkey", "")
        if hotkey:
            return web.json_response(wallet_tracker.get_stats(hotkey))
        return web.json_response(wallet_tracker.summary())

    async def handle_health(req: web.Request) -> web.Response:
        METRICS.vectors_stored.set(store.count())
        METRICS.peers_online.set(router.peer_count())
        return web.json_response({
            "status": "ok",
            "vectors": store.count(),
            "uid": our_uid,
            "peers": router.peer_count(),
        })

    async def handle_metrics(req: web.Request) -> web.Response:
        """Prometheus metrics endpoint — scrape with Prometheus or view in browser."""
        METRICS.vectors_stored.set(store.count())
        METRICS.peers_online.set(router.peer_count())
        return web.Response(
            body=generate_latest(),
            content_type="text/plain",
            charset="utf-8",
        )

    # ── aiohttp server ────────────────────────────────────────────────────────
    app = web.Application()
    app.router.add_post("/IngestSynapse",           handle_ingest)
    app.router.add_post("/QuerySynapse",            handle_query)
    app.router.add_post("/ChallengeSynapse",        handle_challenge)
    app.router.add_get("/health",                   handle_health)
    app.router.add_get("/metrics",                  handle_metrics)
    app.router.add_get("/wallet-stats",             handle_wallet_stats)
    app.router.add_get("/wallet-stats/{hotkey}",    handle_wallet_stats)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    logger.success(f"Miner HTTP server live on 0.0.0.0:{port}")

    # ── Register axon on-chain ────────────────────────────────────────────────
    # bt.Axon is used only for chain registration; we serve JSON ourselves.
    try:
        axon = bt.Axon(wallet=wallet, port=port, ip=external_ip, external_ip=external_ip)
        subtensor.serve_axon(netuid=netuid, axon=axon)
        logger.info(f"Axon registered on-chain | {external_ip}:{port}")
    except Exception as exc:
        logger.warning(f"Chain registration skipped: {exc}")

    # ── Main loop ─────────────────────────────────────────────────────────────
    try:
        while True:
            await asyncio.sleep(60)
            metagraph.sync(subtensor=subtensor)
            router.sync_from_metagraph(
                axons=metagraph.axons, uids=metagraph.uids.tolist()
            )
            logger.debug(
                f"Metagraph synced | vectors={store.count()} | peers={router.peer_count()}"
            )
    except KeyboardInterrupt:
        logger.info("Miner shutting down.")
    finally:
        await runner.cleanup()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

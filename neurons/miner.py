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

import os

# Load env BEFORE any engram imports so config.py reads correct EMBEDDING_DIM
from dotenv import load_dotenv
load_dotenv(os.getenv("ENV_FILE", ".env.miner"), override=True)
load_dotenv(override=False)  # fallback to .env for any missing keys

import asyncio
import hashlib
import hmac as _hmac
import ipaddress
import json
import sqlite3
import struct
import time
from pathlib import Path

import bittensor as bt
from aiohttp import web
from loguru import logger

from engram.config import SUBNET_VERSION
from engram.miner.embedder import get_embedder
from engram.miner.ingest import IngestHandler
from engram.miner.metrics import METRICS, generate_latest
from engram.miner.namespace import NamespaceRegistry
from engram.miner.query import QueryHandler
from engram.miner.auth import AuthError, verify_request
from engram.miner.rate_limiter import RateLimiter
from engram.miner.wallet_tracker import WalletTracker
from engram.miner.store import build_store
from engram.protocol import IngestSynapse, QuerySynapse
from engram.storage.dht import DHTRouter, Peer
from engram.storage.replication import ReplicationManager
from engram.utils.logging import setup_logging

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


# ── Chat history store (SQLite) ───────────────────────────────────────────────

class ChatStore:
    """
    Persists chat history per anonymous user ID in a local SQLite database.
    Thread-safe via check_same_thread=False + WAL mode.
    """

    MAX_MESSAGES = 200  # per user, keeps oldest messages pruned

    def __init__(self, db_path: str = "./data/chats.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                user_id   TEXT NOT NULL,
                ts        INTEGER NOT NULL,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                msg_ts    INTEGER
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id, ts)")
        self._conn.commit()

    def save(self, user_id: str, messages: list[dict]) -> None:
        """Replace all messages for a user (upsert-style)."""
        with self._conn:
            self._conn.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
            now = int(time.time() * 1000)
            rows = [
                (
                    user_id,
                    now + i,
                    m.get("role", "user"),
                    m.get("content", ""),
                    m.get("ts") or (now + i),
                )
                for i, m in enumerate(messages[-self.MAX_MESSAGES:])
            ]
            self._conn.executemany(
                "INSERT INTO chats(user_id, ts, role, content, msg_ts) VALUES(?,?,?,?,?)", rows
            )

    def load(self, user_id: str) -> list[dict]:
        cur = self._conn.execute(
            "SELECT role, content, msg_ts FROM chats WHERE user_id = ? ORDER BY ts ASC",
            (user_id,),
        )
        return [{"role": row[0], "content": row[1], "ts": row[2]} for row in cur.fetchall()]


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
    store              = build_store(backend)
    embedder           = get_embedder()
    ns_registry        = NamespaceRegistry()
    ingest_handler     = IngestHandler(store=store, embedder=embedder,
                                       subtensor=subtensor, netuid=netuid,
                                       namespace_registry=ns_registry)
    query_handler      = QueryHandler(store=store, embedder=embedder,
                                      namespace_registry=ns_registry)
    rate_limiter       = RateLimiter()
    wallet_tracker     = WalletTracker()
    chat_store         = ChatStore(os.getenv("CHAT_DB_PATH", "./data/chats.db"))

    logger.info(f"Vector store: {backend} | {store.count()} vectors loaded")

    # ── Seed ground truth vectors (testnet bootstrap) ─────────────────────────
    gt_path = os.getenv("GROUND_TRUTH_PATH", "./data/ground_truth.jsonl")
    if store.count() == 0 and os.path.exists(gt_path):
        import json
        import numpy as np
        from engram.miner.store import VectorRecord
        seeded = 0
        with open(gt_path) as f:
            for line in f:
                rec = json.loads(line)
                store.upsert(VectorRecord(
                    cid=rec["cid"],
                    embedding=np.array(rec["embedding"], dtype=np.float32),
                    metadata={},
                ))
                seeded += 1
        logger.info(f"Seeded {seeded} ground truth vectors into store")

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

    def _rate_limit_key(req: web.Request, hotkey: str | None) -> str:
        """Use the verified hotkey if present, otherwise fall back to peer IP."""
        if hotkey:
            return hotkey
        peername = req.transport.get_extra_info("peername") if req.transport else None
        return peername[0] if peername else "unknown"

    async def handle_ingest(req: web.Request) -> web.Response:
        import time as _time
        t0 = _time.perf_counter()
        try:
            body = await req.json()

            # ── Auth ─────────────────────────────────────────────────────────
            try:
                caller_hotkey = verify_request(body, "IngestSynapse")
            except AuthError as exc:
                METRICS.ingest_total.labels(status="auth_error").inc()
                return web.json_response({"error": str(exc)}, status=401)

            # Rate-limit every request — keyed by hotkey if provided, else by peer IP.
            # This prevents bypass by simply omitting the hotkey field.
            rl_key = _rate_limit_key(req, caller_hotkey)
            try:
                rate_limiter.check(rl_key)
            except ValueError as exc:
                METRICS.ingest_total.labels(status="rate_limited").inc()
                return web.json_response({"error": str(exc), "hint": "Wait a moment before sending more requests."}, status=429)

            synapse  = IngestSynapse(
                text          = body.get("text"),
                raw_embedding = body.get("raw_embedding"),
                metadata      = body.get("metadata") or {},
                namespace     = body.get("namespace") or None,
                namespace_key = body.get("namespace_key") or None,
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
            return web.json_response({"error": "Internal error — check miner logs."}, status=500)

    async def handle_query(req: web.Request) -> web.Response:
        import time as _time
        t0 = _time.perf_counter()
        try:
            body = await req.json()

            # ── Auth ─────────────────────────────────────────────────────────
            try:
                caller_hotkey = verify_request(body, "QuerySynapse")
            except AuthError as exc:
                METRICS.query_total.labels(status="auth_error").inc()
                return web.json_response({"error": str(exc)}, status=401)

            # ── Rate limit ────────────────────────────────────────────────────
            rl_key = _rate_limit_key(req, caller_hotkey)
            try:
                rate_limiter.check(rl_key)
            except ValueError as exc:
                METRICS.query_total.labels(status="rate_limited").inc()
                return web.json_response({"error": str(exc)}, status=429)

            synapse = QuerySynapse(
                query_text    = body.get("query_text"),
                query_vector  = body.get("query_vector"),
                top_k         = int(body.get("top_k", 10)),
                namespace     = body.get("namespace") or None,
                namespace_key = body.get("namespace_key") or None,
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
            return web.json_response({"error": "Internal error — check miner logs."}, status=500)

    async def handle_challenge(req: web.Request) -> web.Response:
        try:
            body = await req.json()

            # ── Auth — only registered validators should request proofs ───────
            try:
                verify_request(body, "ChallengeSynapse")
            except AuthError as exc:
                return web.json_response({"error": str(exc)}, status=401)

            # ── Rate limit ────────────────────────────────────────────────────
            caller_hotkey = body.get("hotkey")
            rl_key = _rate_limit_key(req, caller_hotkey)
            try:
                rate_limiter.check(rl_key)
            except ValueError as exc:
                return web.json_response({"error": str(exc)}, status=429)

            cid        = body.get("cid", "")
            nonce_hex  = body.get("nonce_hex", "")
            expires_at = int(body.get("expires_at", 0))

            if time.time() > expires_at:
                return web.json_response({"error": "This challenge has expired — the validator will issue a fresh one shortly."}, status=400)

            record = store.get(cid)
            if record is None:
                return web.json_response({"error": f"Nothing stored under that CID ({cid[:20]}…). This miner may not hold a replica of it."}, status=404)

            embedding_hash, proof = _proof_response(nonce_hex, record.embedding.tolist())
            return web.json_response({"embedding_hash": embedding_hash, "proof": proof})

        except Exception as exc:
            logger.error(f"Challenge error: {exc}")
            return web.json_response({"error": "Internal error — check miner logs."}, status=500)

    async def handle_namespace(req: web.Request) -> web.Response:
        """Namespace management — create, delete, rotate key. Localhost only."""
        peername = req.transport.get_extra_info("peername") if req.transport else None
        peer_ip  = peername[0] if peername else ""
        try:
            if not ipaddress.ip_address(peer_ip).is_loopback:
                return web.json_response({"error": "Forbidden"}, status=403)
        except ValueError:
            return web.json_response({"error": "Forbidden"}, status=403)

        try:
            body      = await req.json()
            action    = body.get("action", "")
            namespace = body.get("namespace", "")
            key       = body.get("key", "")
            new_key   = body.get("new_key")

            if action == "create":
                ns_registry.create(namespace, key)
                return web.json_response({"ok": True, "namespace": namespace})

            elif action == "delete":
                ok = ns_registry.delete(namespace, key)
                if not ok:
                    return web.json_response({"error": "Invalid key or namespace not found."}, status=403)
                return web.json_response({"ok": True})

            elif action == "rotate":
                if not new_key:
                    return web.json_response({"error": "new_key is required."}, status=400)
                ok = ns_registry.rotate_key(namespace, key, new_key)
                if not ok:
                    return web.json_response({"error": "Invalid key or namespace not found."}, status=403)
                return web.json_response({"ok": True})

            elif action == "list":
                return web.json_response({"namespaces": ns_registry.list_namespaces()})

            else:
                return web.json_response(
                    {"error": "Unknown action. Use: create, delete, rotate, list"},
                    status=400,
                )
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except Exception as exc:
            logger.error(f"Namespace error: {exc}")
            return web.json_response({"error": "Internal error — check miner logs."}, status=500)

    async def handle_wallet_stats(req: web.Request) -> web.Response:
        # Restrict to loopback — this endpoint exposes all wallet activity data.
        peername = req.transport.get_extra_info("peername") if req.transport else None
        peer_ip  = peername[0] if peername else ""
        try:
            addr = ipaddress.ip_address(peer_ip)
            if not addr.is_loopback:
                return web.json_response({"error": "Forbidden"}, status=403)
        except ValueError:
            return web.json_response({"error": "Forbidden"}, status=403)

        hotkey = req.match_info.get("hotkey", "")
        if hotkey:
            return web.json_response(wallet_tracker.get_stats(hotkey))
        return web.json_response(wallet_tracker.summary())

    async def handle_chat_history_get(req: web.Request) -> web.Response:
        """GET /chat-history/{user_id} — load a user's chat history."""
        user_id = req.match_info.get("user_id", "").strip()
        if not user_id or len(user_id) > 128:
            return web.json_response({"error": "Invalid user_id"}, status=400)
        messages = chat_store.load(user_id)
        return web.json_response({"messages": messages})

    async def handle_chat_history_post(req: web.Request) -> web.Response:
        """POST /chat-history — save a user's chat history."""
        try:
            body = await req.json()
            user_id  = (body.get("user_id") or "").strip()
            messages = body.get("messages") or []
            if not user_id or len(user_id) > 128:
                return web.json_response({"error": "Invalid user_id"}, status=400)
            if not isinstance(messages, list):
                return web.json_response({"error": "messages must be a list"}, status=400)
            chat_store.save(user_id, messages)
            return web.json_response({"ok": True, "saved": len(messages)})
        except Exception as exc:
            logger.error(f"Chat history save error: {exc}")
            return web.json_response({"error": "Internal error"}, status=500)

    async def handle_health(req: web.Request) -> web.Response:
        # Keep health minimal — just a liveness signal, no internal data.
        # Detailed stats are available on /metrics (localhost only).
        return web.json_response({"status": "ok"})

    async def handle_stats(req: web.Request) -> web.Response:
        """Public stats endpoint — basic counters for the dashboard."""
        return web.json_response({
            "status": "ok",
            "vectors": store.count(),
            "peers": router.peer_count(),
            "uid": our_uid,
        })

    async def handle_metrics(req: web.Request) -> web.Response:
        """Prometheus metrics — localhost only to avoid leaking operational data."""
        peername = req.transport.get_extra_info("peername") if req.transport else None
        peer_ip  = peername[0] if peername else ""
        try:
            if not ipaddress.ip_address(peer_ip).is_loopback:
                return web.json_response({"error": "Forbidden"}, status=403)
        except ValueError:
            return web.json_response({"error": "Forbidden"}, status=403)

        METRICS.vectors_stored.set(store.count())
        METRICS.peers_online.set(router.peer_count())
        return web.Response(
            body=generate_latest(),
            content_type="text/plain",
            charset="utf-8",
        )

    # ── aiohttp server ────────────────────────────────────────────────────────
    # 10 MB limit: enough for a 1536-d float32 embedding (~6 KB) with generous headroom.
    # Prevents OOM from oversized request bodies.
    _MAX_BODY = int(os.getenv("MINER_MAX_BODY_BYTES", str(10 * 1024 * 1024)))
    app = web.Application(client_max_size=_MAX_BODY)
    app.router.add_post("/IngestSynapse",           handle_ingest)
    app.router.add_post("/QuerySynapse",            handle_query)
    app.router.add_post("/ChallengeSynapse",        handle_challenge)
    app.router.add_post("/namespace",               handle_namespace)
    app.router.add_get("/chat-history/{user_id}",   handle_chat_history_get)
    app.router.add_post("/chat-history",            handle_chat_history_post)
    app.router.add_get("/health",                   handle_health)
    app.router.add_get("/stats",                    handle_stats)
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

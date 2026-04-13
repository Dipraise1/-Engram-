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
    Supports multiple named conversations per user via conv_id.
    """

    MAX_MESSAGES = 200  # per conversation

    def __init__(self, db_path: str = "./data/chats.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        # conversations table — one row per named conversation
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                conv_id   TEXT NOT NULL,
                user_id   TEXT NOT NULL,
                title     TEXT NOT NULL DEFAULT 'New Chat',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (conv_id)
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at DESC)")
        # chats table — messages keyed by user_id + optional conv_id
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                user_id   TEXT NOT NULL,
                conv_id   TEXT,
                ts        INTEGER NOT NULL,
                role      TEXT NOT NULL,
                content   TEXT NOT NULL,
                msg_ts    INTEGER
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id, ts)")
        self._conn.commit()
        # Migrate: add conv_id column to existing chats if missing (must run BEFORE the index)
        try:
            self._conn.execute("ALTER TABLE chats ADD COLUMN conv_id TEXT")
            self._conn.commit()
        except Exception:
            pass  # column already exists
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_chats_conv ON chats(conv_id, ts)")
        self._conn.commit()

    # ── Conversations ─────────────────────────────────────────────────────────

    def list_conversations(self, user_id: str) -> list[dict]:
        """Return conversations for user, newest first."""
        cur = self._conn.execute(
            "SELECT conv_id, title, created_at, updated_at FROM conversations "
            "WHERE user_id = ? ORDER BY updated_at DESC LIMIT 50",
            (user_id,),
        )
        return [
            {"conv_id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]}
            for r in cur.fetchall()
        ]

    def create_conversation(self, user_id: str, conv_id: str, title: str = "New Chat") -> None:
        now = int(time.time() * 1000)
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO conversations(conv_id, user_id, title, created_at, updated_at) VALUES(?,?,?,?,?)",
                (conv_id, user_id, title, now, now),
            )

    def rename_conversation(self, conv_id: str, user_id: str, title: str) -> None:
        now = int(time.time() * 1000)
        with self._conn:
            self._conn.execute(
                "UPDATE conversations SET title=?, updated_at=? WHERE conv_id=? AND user_id=?",
                (title[:80], now, conv_id, user_id),
            )

    def delete_conversation(self, conv_id: str, user_id: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM conversations WHERE conv_id=? AND user_id=?", (conv_id, user_id)
            )
            self._conn.execute(
                "DELETE FROM chats WHERE conv_id=? AND user_id=?", (conv_id, user_id)
            )

    # ── Messages ──────────────────────────────────────────────────────────────

    def save(self, user_id: str, messages: list[dict], conv_id: str | None = None) -> None:
        """Replace all messages for a user/conversation (upsert-style)."""
        with self._conn:
            if conv_id:
                self._conn.execute(
                    "DELETE FROM chats WHERE user_id = ? AND conv_id = ?", (user_id, conv_id)
                )
            else:
                self._conn.execute(
                    "DELETE FROM chats WHERE user_id = ? AND conv_id IS NULL", (user_id,)
                )
            now = int(time.time() * 1000)
            rows = [
                (
                    user_id,
                    conv_id,
                    now + i,
                    m.get("role", "user"),
                    m.get("content", ""),
                    m.get("ts") or (now + i),
                )
                for i, m in enumerate(messages[-self.MAX_MESSAGES:])
            ]
            self._conn.executemany(
                "INSERT INTO chats(user_id, conv_id, ts, role, content, msg_ts) VALUES(?,?,?,?,?,?)", rows
            )
            # bump conversation updated_at if conv_id given
            if conv_id and messages:
                ts = messages[-1].get("ts") or now
                self._conn.execute(
                    "UPDATE conversations SET updated_at=? WHERE conv_id=? AND user_id=?",
                    (ts, conv_id, user_id),
                )
                # Auto-title: use first user message truncated if title is still default
                cur = self._conn.execute(
                    "SELECT title FROM conversations WHERE conv_id=? AND user_id=?", (conv_id, user_id)
                )
                row = cur.fetchone()
                if row and row[0] in ("New Chat", ""):
                    first_user = next((m["content"] for m in messages if m.get("role") == "user"), None)
                    if first_user:
                        auto_title = first_user[:50] + ("…" if len(first_user) > 50 else "")
                        self._conn.execute(
                            "UPDATE conversations SET title=? WHERE conv_id=? AND user_id=?",
                            (auto_title, conv_id, user_id),
                        )

    def load(self, user_id: str, conv_id: str | None = None) -> list[dict]:
        if conv_id:
            cur = self._conn.execute(
                "SELECT role, content, msg_ts FROM chats WHERE user_id = ? AND conv_id = ? ORDER BY ts ASC",
                (user_id, conv_id),
            )
        else:
            cur = self._conn.execute(
                "SELECT role, content, msg_ts FROM chats WHERE user_id = ? AND conv_id IS NULL ORDER BY ts ASC",
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

    # ── FAISS persistence: load existing index from disk ─────────────────────
    index_path   = os.getenv("FAISS_INDEX_PATH", "./data/miner.index")
    _ingest_count = 0
    SAVE_EVERY    = int(os.getenv("FAISS_SAVE_EVERY", "25"))  # auto-save every N ingests

    if os.path.exists(index_path + ".meta.json"):
        try:
            store.load(index_path)
            logger.info(f"FAISS: loaded {store.count()} vectors from {index_path}")
        except Exception as exc:
            logger.warning(f"FAISS load failed ({exc}) — starting with empty index")

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

    # ── Runtime stat counters ─────────────────────────────────────────────────
    _queries_today      = 0
    _query_day_start    = int(time.time() // 86400)   # day bucket
    _latency_window: list[float] = []                 # rolling last-100 query latencies (ms)
    _challenge_total    = 0
    _challenge_ok       = 0
    _miner_start_ts     = time.time()

    # ── HTTP handlers ─────────────────────────────────────────────────────────

    def _rate_limit_key(req: web.Request, hotkey: str | None) -> str:
        """Use the verified hotkey if present, otherwise fall back to peer IP."""
        if hotkey:
            return hotkey
        peername = req.transport.get_extra_info("peername") if req.transport else None
        return peername[0] if peername else "unknown"

    async def handle_ingest(req: web.Request) -> web.Response:
        nonlocal _ingest_count
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
                _ingest_count += 1
                if _ingest_count % SAVE_EVERY == 0:
                    try:
                        store.save(index_path)
                        logger.debug(f"FAISS auto-saved ({store.count()} vectors)")
                    except Exception as exc:
                        logger.warning(f"FAISS auto-save failed: {exc}")
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
        nonlocal _queries_today, _query_day_start, _latency_window
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
            # ── Rolling stat tracking ────────────────────────────────────────
            today_bucket = int(_time.time() // 86400)
            if today_bucket != _query_day_start:
                _queries_today = 0
                _query_day_start = today_bucket
            _queries_today += 1
            _latency_window.append(elapsed_ms)
            if len(_latency_window) > 100:
                _latency_window.pop(0)
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
        nonlocal _challenge_total, _challenge_ok
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
            _challenge_total += 1
            _challenge_ok += 1
            return web.json_response({"embedding_hash": embedding_hash, "proof": proof})

        except Exception as exc:
            _challenge_total += 1   # count the failure too
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
        """GET /chat-history/{user_id}?conv_id=X — load a user's chat history."""
        user_id = req.match_info.get("user_id", "").strip()
        conv_id = req.rel_url.query.get("conv_id", "").strip() or None
        if not user_id or len(user_id) > 128:
            return web.json_response({"error": "Invalid user_id"}, status=400)
        messages = chat_store.load(user_id, conv_id)
        return web.json_response({"messages": messages})

    async def handle_chat_history_post(req: web.Request) -> web.Response:
        """POST /chat-history — save a user's chat history."""
        try:
            body = await req.json()
            user_id  = (body.get("user_id") or "").strip()
            conv_id  = (body.get("conv_id") or "").strip() or None
            messages = body.get("messages") or []
            if not user_id or len(user_id) > 128:
                return web.json_response({"error": "Invalid user_id"}, status=400)
            if not isinstance(messages, list):
                return web.json_response({"error": "messages must be a list"}, status=400)
            chat_store.save(user_id, messages, conv_id)
            return web.json_response({"ok": True, "saved": len(messages)})
        except Exception as exc:
            logger.error(f"Chat history save error: {exc}")
            return web.json_response({"error": "Internal error"}, status=500)

    async def handle_conversations_get(req: web.Request) -> web.Response:
        """GET /conversations/{user_id} — list all conversations for a user."""
        user_id = req.match_info.get("user_id", "").strip()
        if not user_id or len(user_id) > 128:
            return web.json_response({"error": "Invalid user_id"}, status=400)
        convs = chat_store.list_conversations(user_id)
        return web.json_response({"conversations": convs})

    async def handle_conversations_post(req: web.Request) -> web.Response:
        """POST /conversations — create a new conversation."""
        try:
            body    = await req.json()
            user_id = (body.get("user_id") or "").strip()
            conv_id = (body.get("conv_id") or "").strip()
            title   = (body.get("title") or "New Chat").strip()[:80]
            if not user_id or not conv_id or len(user_id) > 128 or len(conv_id) > 128:
                return web.json_response({"error": "Invalid user_id or conv_id"}, status=400)
            chat_store.create_conversation(user_id, conv_id, title)
            return web.json_response({"ok": True})
        except Exception as exc:
            logger.error(f"Conversation create error: {exc}")
            return web.json_response({"error": "Internal error"}, status=500)

    async def handle_conversations_patch(req: web.Request) -> web.Response:
        """PATCH /conversations/{conv_id} — rename a conversation."""
        try:
            conv_id = req.match_info.get("conv_id", "").strip()
            body    = await req.json()
            user_id = (body.get("user_id") or "").strip()
            title   = (body.get("title") or "").strip()[:80]
            if not user_id or not conv_id or not title:
                return web.json_response({"error": "Invalid params"}, status=400)
            chat_store.rename_conversation(conv_id, user_id, title)
            return web.json_response({"ok": True})
        except Exception as exc:
            logger.error(f"Conversation rename error: {exc}")
            return web.json_response({"error": "Internal error"}, status=500)

    async def handle_conversations_delete(req: web.Request) -> web.Response:
        """DELETE /conversations/{conv_id}?user_id=X — delete a conversation."""
        conv_id = req.match_info.get("conv_id", "").strip()
        user_id = req.rel_url.query.get("user_id", "").strip()
        if not user_id or not conv_id:
            return web.json_response({"error": "Invalid params"}, status=400)
        chat_store.delete_conversation(conv_id, user_id)
        return web.json_response({"ok": True})

    async def handle_health(req: web.Request) -> web.Response:
        # Keep health minimal — just a liveness signal, no internal data.
        # Detailed stats are available on /metrics (localhost only).
        return web.json_response({"status": "ok"})

    async def handle_stats(req: web.Request) -> web.Response:
        """Public stats endpoint — rich counters for the dashboard."""
        import statistics as _stats
        p50_latency = (
            round(_stats.median(_latency_window), 1) if _latency_window else None
        )
        proof_rate = (
            round(_challenge_ok / _challenge_total, 4) if _challenge_total > 0 else None
        )
        uptime_pct = round(
            min(1.0, (time.time() - _miner_start_ts) / 86400), 4
        )  # fraction of last 24h this process has been up
        # Best-effort block height — non-blocking
        try:
            block = subtensor.get_current_block()
        except Exception:
            block = None
        # Best-effort avg score from metagraph incentive (what miners actually earn)
        try:
            scores = [float(x) for x in metagraph.incentive.tolist() if float(x) > 0]
            avg_score = round(sum(scores) / len(scores), 4) if scores else None
        except Exception:
            avg_score = None
        return web.json_response({
            "status": "ok",
            "vectors": store.count(),
            "peers": router.peer_count(),
            "uid": our_uid,
            "queries_today": _queries_today,
            "p50_latency_ms": p50_latency,
            "proof_rate": proof_rate,
            "uptime_pct": uptime_pct,
            "block": block,
            "avg_score": avg_score,
            "hotkey": wallet.hotkey.ss58_address,
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
    app.router.add_get("/conversations/{user_id}",  handle_conversations_get)
    app.router.add_post("/conversations",           handle_conversations_post)
    app.router.add_patch("/conversations/{conv_id}", handle_conversations_patch)
    app.router.add_delete("/conversations/{conv_id}", handle_conversations_delete)
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
        try:
            store.save(index_path)
            logger.info(f"FAISS: saved {store.count()} vectors on shutdown → {index_path}")
        except Exception as exc:
            logger.warning(f"FAISS shutdown save failed: {exc}")
        await runner.cleanup()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

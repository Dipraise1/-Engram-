"""
Engram — Validator Neuron

Periodically:
  1. Queries miners with ground truth vectors → scores recall@K
  2. Issues storage proof challenges → tracks proof success rate
  3. Sets weights on-chain via Bittensor
"""

import os

# Load env BEFORE any engram imports so config.py reads correct EMBEDDING_DIM
from dotenv import load_dotenv
load_dotenv(os.getenv("ENV_FILE", ".env.validator"), override=True)
load_dotenv(override=False)  # fallback to .env for any missing keys

import asyncio
import ipaddress
import time

import bittensor as bt
import nest_asyncio

nest_asyncio.apply()


# ── Python 3.14 / aiohttp compatibility patch ─────────────────────────────────
# Both asyncio.Timeout and aiohttp.TimerContext require current_task() != None.
# bittensor's dendrite triggers this on Python 3.14. Patch both to no-op when
# not inside a task so HTTP requests proceed without cancellation support.

import asyncio.timeouts as _asyncio_timeouts
import aiohttp.helpers as _aiohttp_helpers


class _NoopTimeout:
    """Drop-in for asyncio.Timeout that works outside Task context."""
    def __init__(self, when): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *a): return False
    def reschedule(self, when): pass
    @property
    def deadline(self): return None
    def expired(self): return False


_OrigTimeout = _asyncio_timeouts.Timeout


class _PatchedAsyncioTimeout(_OrigTimeout):
    async def __aenter__(self):
        try:
            return await super().__aenter__()
        except RuntimeError:
            return self


_asyncio_timeouts.Timeout = _PatchedAsyncioTimeout
asyncio.timeout = lambda delay: _PatchedAsyncioTimeout(delay)


class _PatchedTimerContext(_aiohttp_helpers.TimerContext):
    def __enter__(self):
        try:
            return super().__enter__()
        except RuntimeError:
            return self


_aiohttp_helpers.TimerContext = _PatchedTimerContext
from loguru import logger

from engram.config import CHALLENGE_INTERVAL_SECS, RECALL_K, SUBNET_VERSION
from engram.validator.challenge import ChallengeDispatcher
from engram.validator.ground_truth import GroundTruthManager
from engram.validator.reward import RewardManager
from engram.validator.scorer import recall_at_k
from engram.storage.dht import DHTRouter, Peer
from engram.storage.replication import ReplicationManager
from engram.utils.logging import setup_logging

setup_logging(os.getenv("LOG_LEVEL", "INFO"))

EVAL_INTERVAL = 120   # seconds between scoring rounds
WEIGHT_INTERVAL = 600 # seconds between weight-setting


def _http_post_sync(url: str, payload: dict, timeout: float) -> dict | None:
    """Synchronous HTTP POST — runs in a thread to avoid nest_asyncio/aiohttp conflicts."""
    import urllib.request as _urllib
    import json as _json
    try:
        data = _json.dumps(payload).encode()
        req = _urllib.Request(url, data=data,
                              headers={"Content-Type": "application/json"}, method="POST")
        with _urllib.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return _json.loads(resp.read())
    except Exception as e:
        logger.debug(f"Direct axon query failed {url}: {e}")
    return None


def _is_routable_ip(ip: str) -> bool:
    """Return True only for globally-routable IPs — blocks SSRF via private/loopback addresses."""
    try:
        addr = ipaddress.ip_address(ip)
        return not (
            addr.is_loopback
            or addr.is_private
            or addr.is_link_local
            or addr.is_multicast
            or addr.is_reserved
            or addr.is_unspecified
        )
    except ValueError:
        return False


async def query_axon_direct(
    ip: str,
    port: int,
    synapse_name: str,
    payload: dict,
    timeout: float = 30.0,
    allow_private: bool = False,
) -> dict | None:
    """Direct HTTP call to a miner axon — runs synchronous urllib in a thread pool.

    allow_private should only be True for explicitly configured local-dev fallbacks,
    never for IPs sourced from the metagraph.
    """
    if not allow_private and not _is_routable_ip(ip):
        logger.warning(f"Blocked SSRF attempt — refusing to query non-routable IP: {ip}")
        return None
    if not (1 <= port <= 65535):
        logger.warning(f"Blocked query to invalid port {port}")
        return None
    url = f"http://{ip}:{port}/{synapse_name}"
    return await asyncio.get_event_loop().run_in_executor(
        None, _http_post_sync, url, payload, timeout
    )


async def run() -> None:
    wallet_name   = os.getenv("WALLET_NAME", "default")
    wallet_hotkey = os.getenv("WALLET_HOTKEY", "default")
    network       = os.getenv("SUBTENSOR_ENDPOINT") or os.getenv("SUBTENSOR_NETWORK", "test")
    netuid        = int(os.getenv("NETUID", "99"))
    gt_path       = os.getenv("GROUND_TRUTH_PATH", "./data/ground_truth.jsonl")
    # Fallback port used when metagraph axon.port is 0 (serve_axon not yet updated on-chain).
    # Useful during local dev when the tx rate limit hasn't elapsed.
    fallback_miner_port = int(os.getenv("MINER_PORT", "8091"))
    fallback_miner_ip   = os.getenv("MINER_IP", "127.0.0.1")

    logger.info(f"Engram Validator v{SUBNET_VERSION} | network={network} | netuid={netuid}")

    # ── Bittensor setup ───────────────────────────────────────────────────────
    wallet = bt.Wallet(name=wallet_name, hotkey=wallet_hotkey)
    subtensor = bt.Subtensor(network=network)
    metagraph = subtensor.metagraph(netuid=netuid)

    # ── Components ────────────────────────────────────────────────────────────
    ground_truth = GroundTruthManager(path=gt_path)
    challenge_dispatcher = ChallengeDispatcher()
    reward_manager = RewardManager(subtensor=subtensor, wallet=wallet, netuid=netuid)

    for cid in ground_truth.all_cids():
        challenge_dispatcher.register_cid(cid)

    # ── DHT + Replication tracking ────────────────────────────────────────────
    local_peer = Peer(uid=0, hotkey=wallet.hotkey.ss58_address)
    router = DHTRouter(local_peer=local_peer)
    router.sync_from_metagraph(axons=metagraph.axons, uids=metagraph.uids.tolist())
    replication_mgr = ReplicationManager(router=router)
    # Pre-register all ground-truth CIDs
    for cid in ground_truth.all_cids():
        replication_mgr.register(cid)

    logger.info(f"Ground truth entries: {len(ground_truth)}")

    recall_scores: dict[int, float] = {}
    latency_scores: dict[int, float | None] = {}

    last_eval = 0.0
    last_weight_set = 0.0
    last_challenge = 0.0

    try:
        while True:
            now = time.time()
            metagraph.sync(subtensor=subtensor)
            axons = metagraph.axons
            uids = metagraph.uids.tolist()
            router.sync_from_metagraph(axons=axons, uids=uids)

            # ── Scoring round ─────────────────────────────────────────────────
            if now - last_eval >= EVAL_INTERVAL:
                last_eval = now
                sample = ground_truth.sample(n=5)

                for entry in sample:
                    payload = {
                        "query_vector": entry.embedding.tolist(),
                        "top_k": RECALL_K,
                    }

                    for uid, axon in zip(uids, axons):
                        t0 = time.time()
                        # Use metagraph IP if valid and routable; fall back to local dev IP.
                        # allow_private=True only for the explicitly configured fallback, never
                        # for IPs sourced from the metagraph (prevents SSRF via chain data).
                        _axon_ip   = axon.ip if axon.ip not in ("0.0.0.0", "0") else None
                        _use_ip    = _axon_ip if _axon_ip and _is_routable_ip(_axon_ip) else fallback_miner_ip
                        _use_port  = axon.port or fallback_miner_port
                        _is_local  = _use_ip == fallback_miner_ip
                        data = await query_axon_direct(
                            ip=_use_ip,
                            port=_use_port,
                            synapse_name="QuerySynapse",
                            payload=payload,
                            timeout=30.0,
                            allow_private=_is_local,
                        )
                        latency_ms = (time.time() - t0) * 1000

                        if data is None or data.get("error"):
                            logger.warning(f"Query failed uid={uid} url=http://{_use_ip}:{_use_port}/QuerySynapse data={data}")
                            recall_scores[uid] = 0.0
                            latency_scores[uid] = None
                            continue

                        returned = [
                            r.get("cid")
                            for r in (data.get("results") or [])
                            if isinstance(r, dict) and r.get("cid") is not None
                        ]
                        r = recall_at_k(returned, entry.top_k_cids, k=RECALL_K)
                        recall_scores[uid] = r
                        latency_scores[uid] = data.get("latency_ms") or latency_ms

                logger.info(f"Eval round complete | miners={len(uids)} | recall_scores={dict(recall_scores)}")

            # ── Challenge round ───────────────────────────────────────────────
            if now - last_challenge >= CHALLENGE_INTERVAL_SECS:
                last_challenge = now
                cid = challenge_dispatcher.pick_random_cid()

                if cid:
                    entry = next((e for e in ground_truth._entries if e.cid == cid), None)
                    challenge = challenge_dispatcher.build_challenge(cid)

                    if challenge and entry is not None:
                        challenge_payload = {
                            "cid": challenge.cid,
                            "nonce_hex": challenge.nonce_hex,
                            "expires_at": challenge.expires_at,
                        }

                        for uid, axon in zip(uids, axons):
                            _axon_ip  = axon.ip if axon.ip not in ("0.0.0.0", "0") else None
                            _use_ip   = _axon_ip if _axon_ip and _is_routable_ip(_axon_ip) else fallback_miner_ip
                            _use_port = axon.port or fallback_miner_port
                            _is_local = _use_ip == fallback_miner_ip
                            data = await query_axon_direct(
                                ip=_use_ip,
                                port=_use_port,
                                synapse_name="ChallengeSynapse",
                                payload=challenge_payload,
                                timeout=15.0,
                                allow_private=_is_local,
                            )

                            if data is None or data.get("error"):
                                challenge_dispatcher.record_result(str(uid), passed=False)
                                replication_mgr.unconfirm(cid, int(uid))
                                continue

                            passed = challenge_dispatcher.verify_response(
                                challenge=challenge,
                                response_embedding_hash=data.get("embedding_hash") or "",
                                response_proof=data.get("proof") or "",
                                expected_embedding=entry.embedding.tolist(),
                            )
                            challenge_dispatcher.record_result(str(uid), passed=passed)
                            if passed:
                                replication_mgr.confirm(cid, int(uid))
                            else:
                                replication_mgr.unconfirm(cid, int(uid))

            # ── Weight setting ────────────────────────────────────────────────
            if now - last_weight_set >= WEIGHT_INTERVAL:
                last_weight_set = now
                proof_rates: dict[int, float] = {}
                for uid in uids:
                    record = challenge_dispatcher._records.get(str(uid))  # type: ignore[attr-defined]
                    proof_rates[int(uid)] = record.success_rate if record else 0.0
                reward_manager.set_weights(
                    metagraph=metagraph,
                    recall_scores=recall_scores,
                    latency_scores=latency_scores,
                    proof_rates=proof_rates,
                )

            await asyncio.sleep(10)

    except KeyboardInterrupt:
        logger.info("Validator shutting down.")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

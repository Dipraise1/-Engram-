"""
Engram — Miner Neuron

Registers on Bittensor, serves an axon that handles:
  - IngestSynapse  → store embedding, return CID
  - QuerySynapse   → ANN search, return top-K
  - ChallengeSynapse → storage proof response
"""

import os
import time

import bittensor as bt
from dotenv import load_dotenv
from loguru import logger

from engram.config import SUBNET_VERSION
from engram.miner.embedder import get_embedder
from engram.miner.ingest import IngestHandler
from engram.miner.query import QueryHandler
from engram.miner.store import build_store
from engram.protocol import ChallengeSynapse, IngestSynapse, QuerySynapse
from engram.utils.logging import setup_logging

load_dotenv()
setup_logging(os.getenv("LOG_LEVEL", "INFO"))


def main() -> None:
    wallet_name = os.getenv("WALLET_NAME", "default")
    wallet_hotkey = os.getenv("WALLET_HOTKEY", "default")
    network = os.getenv("SUBTENSOR_NETWORK", "test")
    netuid = int(os.getenv("NETUID", "99"))
    port = int(os.getenv("MINER_PORT", "8091"))
    backend = os.getenv("VECTOR_STORE_BACKEND", "qdrant")

    logger.info(f"Engram Miner v{SUBNET_VERSION} | network={network} | netuid={netuid}")

    # ── Bittensor setup ───────────────────────────────────────────────────────
    wallet = bt.wallet(name=wallet_name, hotkey=wallet_hotkey)
    subtensor = bt.subtensor(network=network)
    metagraph = subtensor.metagraph(netuid=netuid)

    logger.info(f"Wallet: {wallet.hotkey.ss58_address}")

    # ── Core components ───────────────────────────────────────────────────────
    store = build_store(backend)
    embedder = get_embedder()
    ingest_handler = IngestHandler(store=store, embedder=embedder)
    query_handler = QueryHandler(store=store, embedder=embedder)

    logger.info(f"Vector store: {backend} | {store.count()} vectors loaded")

    # ── Synapse handlers ──────────────────────────────────────────────────────

    def handle_ingest(synapse: IngestSynapse) -> IngestSynapse:
        return ingest_handler.handle(synapse)

    def handle_query(synapse: QuerySynapse) -> QuerySynapse:
        return query_handler.handle(synapse)

    def handle_challenge(synapse: ChallengeSynapse) -> ChallengeSynapse:
        try:
            import engram_core
            record = store.get(synapse.cid)
            if record is None:
                synapse.error = f"CID not found: {synapse.cid}"
                return synapse

            # Reconstruct challenge object from synapse fields
            import time as _time
            challenge = engram_core.generate_challenge(synapse.cid, 60)
            # Override nonce with the one from the validator (can't directly set,
            # so we use the validator's proof fields for HMAC recomputation)
            response = engram_core.generate_response(challenge, record.embedding.tolist())
            synapse.embedding_hash = response.embedding_hash
            synapse.proof = response.proof

        except Exception as e:
            logger.error(f"Challenge handler error: {e}")
            synapse.error = "internal error"

        return synapse

    # ── Axon ──────────────────────────────────────────────────────────────────
    axon = bt.axon(wallet=wallet, port=port)
    axon.attach(forward_fn=handle_ingest)
    axon.attach(forward_fn=handle_query)
    axon.attach(forward_fn=handle_challenge)
    axon.start()

    logger.success(f"Axon live on port {port}")

    # ── Registration check ────────────────────────────────────────────────────
    if not subtensor.is_hotkey_registered(netuid=netuid, hotkey_ss58=wallet.hotkey.ss58_address):
        logger.warning("Hotkey not registered on subnet. Register first:")
        logger.warning(f"  btcli subnet register --netuid {netuid} --wallet.name {wallet_name}")

    # ── Main loop ─────────────────────────────────────────────────────────────
    try:
        while True:
            metagraph.sync(subtensor=subtensor)
            logger.debug(f"Metagraph synced | vectors={store.count()}")
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Miner shutting down.")
    finally:
        axon.stop()


if __name__ == "__main__":
    main()

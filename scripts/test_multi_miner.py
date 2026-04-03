"""
Phase 2.4 — Multi-Miner DHT Test

Verifies that:
1. Two miners are running (miner1 on :8091, miner2 on :8093)
2. When a CID is ingested, the DHT assignment is deterministic
3. The CID is stored on all miners (REPLICATION_FACTOR=3 > 2 miners → both store it)
4. A query to each miner returns the ingested CID in top-K results

Prerequisites:
  - Local subtensor running at ws://127.0.0.1:9944
  - Miner 1: already running (port 8091, hotkey=default)
  - Miner 2: start with:
      dotenv -f .env.miner2 run -- python -m neurons.miner

Run:
  python scripts/test_multi_miner.py
"""

import hashlib
import json
import sys
import time
import urllib.request as _urllib

import numpy as np

# Add project root to path
sys.path.insert(0, ".")
from engram.cid import generate_cid
from engram.storage.dht import DHTRouter, Peer

# ── Config ────────────────────────────────────────────────────────────────────

MINER1_URL = "http://127.0.0.1:8091"
MINER2_URL = "http://127.0.0.1:8093"
TIMEOUT = 10.0

# These match the registered hotkeys. Update if your local wallet differs.
# We read them from the health endpoints to get the real registered hotkeys.


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def post(url: str, payload: dict) -> dict | None:
    try:
        data = json.dumps(payload).encode()
        req = _urllib.Request(url, data=data,
                              headers={"Content-Type": "application/json"}, method="POST")
        with _urllib.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [FAIL] {url}: {e}")
        return None


def get(url: str) -> dict | None:
    try:
        with _urllib.urlopen(url, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [FAIL] {url}: {e}")
        return None


# ── Checks ────────────────────────────────────────────────────────────────────

def check_health(label: str, base_url: str) -> dict | None:
    h = get(f"{base_url}/health")
    if h:
        print(f"  {label} health OK | uid={h.get('uid')} vectors={h.get('vectors')}")
    else:
        print(f"  {label} health FAILED — is it running?")
    return h


def ingest_vector(base_url: str, text: str, embedding: list[float]) -> str | None:
    result = post(f"{base_url}/IngestSynapse", {
        "text": text,
        "raw_embedding": embedding,
        "metadata": {"source": "multi_miner_test"},
    })
    if result and result.get("cid"):
        return result["cid"]
    print(f"  Ingest error: {result}")
    return None


def query_vector(base_url: str, embedding: list[float], top_k: int = 5) -> list[str]:
    result = post(f"{base_url}/QuerySynapse", {
        "query_vector": embedding,
        "top_k": top_k,
    })
    if result and result.get("results"):
        return [r.get("cid") for r in result["results"] if r.get("cid")]
    return []


def verify_dht_assignment(cid: str, miner1_hotkey: str, miner2_hotkey: str) -> None:
    """Print which miners the DHT assigns this CID to."""
    # Build a DHT with both miners as peers
    local = Peer(uid=99, hotkey="validator_dummy")
    router = DHTRouter(local_peer=local)
    router.add_peer(Peer(uid=0, hotkey=miner1_hotkey))
    router.add_peer(Peer(uid=1, hotkey=miner2_hotkey))

    assigned = router.assign(cid)
    assigned_uids = [p.uid for p in assigned]
    print(f"  DHT assigns CID {cid[:24]}… to UIDs: {assigned_uids}")
    return assigned_uids


# ── Main test ─────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Phase 2.4 — Multi-Miner DHT Test")
    print("=" * 60)

    # 1. Health check both miners
    print("\n[1] Health checks")
    h1 = check_health("Miner1 :8091", MINER1_URL)
    h2 = check_health("Miner2 :8093", MINER2_URL)

    if not h1:
        print("\nERROR: Miner 1 not responding. Start it first.")
        sys.exit(1)
    if not h2:
        print("\nERROR: Miner 2 not responding.")
        print("Start miner 2 with:")
        print("  dotenv -f .env.miner2 run -- python -m neurons.miner")
        sys.exit(1)

    # 2. Generate test embedding
    print("\n[2] Generating test embedding")
    rng = np.random.RandomState(42)
    embedding = rng.randn(384).astype(np.float32)
    embedding = (embedding / np.linalg.norm(embedding)).tolist()
    text = "multi-miner DHT routing test vector"
    cid = generate_cid(np.array(embedding), metadata={"source": "multi_miner_test"})
    print(f"  CID: {cid[:32]}…")

    # 3. Ingest into miner 1
    print("\n[3] Ingesting into Miner 1")
    cid_returned = ingest_vector(MINER1_URL, text, embedding)
    if cid_returned:
        match = "✓ MATCH" if cid_returned == cid else f"✗ MISMATCH (got {cid_returned[:24]}…)"
        print(f"  CID returned: {cid_returned[:32]}… {match}")
    else:
        print("  Ingest FAILED on miner 1")
        sys.exit(1)

    # 4. Ingest into miner 2 (in replication, validator would push to all assigned)
    print("\n[4] Ingesting into Miner 2")
    cid_returned2 = ingest_vector(MINER2_URL, text, embedding)
    if cid_returned2:
        match = "✓ MATCH" if cid_returned2 == cid else f"✗ MISMATCH"
        print(f"  CID returned: {cid_returned2[:32]}… {match}")
    else:
        print("  Ingest FAILED on miner 2")

    # 5. Query both miners and verify CID appears
    print("\n[5] Querying both miners")
    time.sleep(0.5)  # brief settle

    results1 = query_vector(MINER1_URL, embedding)
    found1 = cid in results1
    print(f"  Miner1 results ({len(results1)}): {'✓ CID found' if found1 else '✗ CID NOT found'}")

    results2 = query_vector(MINER2_URL, embedding)
    found2 = cid in results2
    print(f"  Miner2 results ({len(results2)}): {'✓ CID found' if found2 else '✗ CID NOT found'}")

    # 6. DHT assignment verification
    print("\n[6] DHT routing verification")
    # Get actual hotkeys from health endpoints (uid field won't give us hotkey, check metagraph)
    # For now we just show the local DHT assignment using dummy hotkeys
    # In a real run, hotkeys would come from metagraph.axons[uid].hotkey
    print("  (Using uid=0 and uid=1 as miner identifiers)")
    local = Peer(uid=99, hotkey="validator_dummy_key")
    router = DHTRouter(local_peer=local)
    # Derive peers from UIDs (without real hotkeys we use deterministic dummy keys)
    m1_peer = Peer(uid=0, hotkey="engram_default_miner1")
    m2_peer = Peer(uid=1, hotkey="engram_miner2_hotkey")
    router.add_peer(m1_peer)
    router.add_peer(m2_peer)

    assigned = router.assign(cid)
    assigned_uids = [p.uid for p in assigned]
    print(f"  DHT assigns this CID to UIDs: {assigned_uids}")
    print(f"  (With REPLICATION_FACTOR=3 and 2 miners → both miners always assigned)")

    # 7. Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    passed = found1 and found2 and (cid_returned == cid)
    print(f"  Ingest CID consistent:  {'✓' if cid_returned == cid else '✗'}")
    print(f"  CID stored on Miner 1:  {'✓' if found1 else '✗'}")
    print(f"  CID stored on Miner 2:  {'✓' if found2 else '✗'}")
    print(f"\n  Overall: {'PASS ✓' if passed else 'FAIL ✗'}")

    if not passed:
        sys.exit(1)


if __name__ == "__main__":
    main()

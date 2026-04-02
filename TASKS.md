# Engram — v1.0 Task Tracker

Decentralized Vector Database Subnet on Bittensor.
Track every milestone from local chain → testnet → mainnet launch.

---

## PHASE 0 — Local Chain & Registration
> Get the subnet live on a local subtensor node

- [x] **0.1** Subtensor build completes
      Binary: `target/fast-runtime/release/node-subtensor` (75MB, built 2026-04-03)

- [x] **0.2** Start local subtensor chain
      Running at ws://127.0.0.1:9944 ✓

- [x] **0.3** Fund engram wallet from Alice (local chain)
      `python scripts/fund_from_alice.py` → τ2,000 transferred ✓

- [x] **0.4** Register Engram subnet on local chain
      `python scripts/register_local_subnet.py` → **NETUID = 2** ✓

- [x] **0.5** Register validator hotkey on subnet
      uid=0 on netuid=2, hotkey: 5GYsnNdg... ✓

- [x] **0.6** Generate ownership proof
      message_and_signature.txt generated ✓
      Signed by: 5FHGPfix... (coldkey)

---

## PHASE 1 — Neurons Running End-to-End (Local)
> Miner + validator actually talking over the Bittensor protocol

- [ ] **1.1** Start miner neuron
      `python neurons/miner.py`
      Verify: axon serving on port 8091, registered on metagraph

- [ ] **1.2** Start validator neuron
      `python neurons/validator.py`
      Verify: queries miner, sets weights on chain

- [ ] **1.3** Ingest vectors via CLI
      `engram ingest "sample text"` or `engram ingest --file data/sample.jsonl`
      Verify: CID returned, stored in FAISS

- [ ] **1.4** Query vectors via CLI
      `engram query "semantic search query"`
      Verify: results with scores returned

- [ ] **1.5** Storage proofs working
      Validator issues ChallengeSynapse → miner responds → proof verified
      Check validator logs for `proof_rate > 0`

- [ ] **1.6** Weight-setting on chain
      Validator sets miner weights every 600s
      Verify with: `btcli subnet weights --netuid <N>`

- [ ] **1.7** Full scoring loop verified
      `score = 0.50·recall@K + 0.30·latency + 0.20·proof_rate`
      Run `python scripts/run_demo.py` → confirm score > 0.80

---

## PHASE 2 — DHT & Replication Wired into Neurons
> CID routing and replication across multiple miners

- [ ] **2.1** Wire DHTRouter into miner neuron
      On startup: `router.sync_from_metagraph(metagraph.axons, metagraph.uids.tolist())`
      On IngestSynapse: check `router.should_store(cid)` before storing

- [ ] **2.2** Wire ReplicationManager into miner
      On successful ingest: `replication_mgr.register(cid, assigned_uids)`
      Confirm replication across miners

- [ ] **2.3** Sync metagraph periodically
      Miner + validator refresh metagraph every 300s
      DHT routing table stays current as miners join/leave

- [ ] **2.4** Multi-miner local test
      Spin up 2 miners on different ports
      Ingest CID → verify it lands on both assigned miners via DHT

- [ ] **2.5** Repair targeting
      Kill one miner → `replication_mgr.handle_miner_offline(uid)`
      Validator detects `ReplicationStatus.DEGRADED` and triggers repair

---

## PHASE 3 — SDK & Developer Experience
> External devs can use Engram programmatically

- [ ] **3.1** SDK client tested against live local neurons
      `from engram.sdk.client import EngramClient`
      `client.ingest("text")`, `client.query("query")` round-trip

- [ ] **3.2** SDK error handling
      Timeouts, miner offline, bad CID — all handled gracefully with clear exceptions

- [ ] **3.3** JSONL batch ingest
      `engram ingest --file ./data/wikipedia_sample.jsonl`
      Ingest 1000+ records, measure throughput

- [ ] **3.4** CLI `engram status` shows live neuron info
      Connect to metagraph, show registered miners, stake, scores

- [ ] **3.5** PyPI package prep
      `pyproject.toml` with correct entry points
      `pip install engram-subnet` installs CLI + SDK

---

## PHASE 4 — Testnet Registration
> Subnet live on Bittensor testnet (finney)

- [ ] **4.1** Acquire testnet TAO
      Need ~1000 TAO for subnet burn
      Sources: Bittensor Discord #faucet, taoswap.org/testnet-faucet
      Current balance: ~20 TAO

- [ ] **4.2** Register subnet on testnet
      `python scripts/register_subnet.py`  (SUBTENSOR_NETWORK=test)
      Expected: NETUID assigned on finney testnet

- [ ] **4.3** Register validator on testnet
      `btcli subnet register --netuid <N> --subtensor.network test`

- [ ] **4.4** Make GitHub repo public
      Required for Discord channel request
      Repo: https://github.com/Dipraise1/-Engram-

- [ ] **4.5** Discord channel registration
      Post in #1107738550373454028 mentioning @kat_defiants
      Message: "Requesting subnet channel for Engram (netuid=<N>)"
      DM message_and_signature.txt to @kat_defiants

- [ ] **4.6** Testnet miner + validator running 24/7
      Deploy to VPS or cloud instance
      Validator sets weights continuously on testnet

---

## PHASE 5 — Rust Core Integration (engram-core)
> High-performance CID and proof logic via PyO3

- [ ] **5.1** Build engram-core wheel
      `cd engram-core && maturin develop --release`
      Verify: `import engram_core; engram_core.generate_cid(...)` works

- [ ] **5.2** Replace Python CID generation with Rust
      Swap `hashlib` CID in `ingest.py` → `engram_core.generate_cid()`
      Benchmark: expect 10-50× speedup on large batches

- [ ] **5.3** Replace Python proof verification with Rust
      `challenge.py` → `engram_core.verify_response()`

- [ ] **5.4** Rust unit tests passing in CI
      `cargo test --no-default-features`
      All 9 tests green

- [ ] **5.5** CI pipeline
      GitHub Actions: `pytest` + `cargo test` on every push to main

---

## PHASE 6 — Production Hardening
> Ready for mainnet miners to join

- [ ] **6.1** Qdrant production setup
      Docker or binary Qdrant on miner
      Switch `VECTOR_STORE_BACKEND=qdrant` in .env
      Verify HNSW params: M=16, ef_construction=200, ef_search=100

- [ ] **6.2** Validator ground truth dataset
      Curated 1000+ query/result pairs in `data/ground_truth.jsonl`
      Used for recall@K scoring

- [ ] **6.3** Anti-spam stake check
      `INGEST_STAKE_TAO=0.001` — reject ingest from wallets with < threshold stake
      Wire into `IngestHandler.handle()`

- [ ] **6.4** Rate limiting
      Per-hotkey ingest rate limit (max N vectors/min)
      Reject with error synapse if exceeded

- [ ] **6.5** Miner incentive documentation
      README section: how scoring works, how to maximize rewards
      Targeting 3-5 external miners joining testnet

- [ ] **6.6** Monitoring
      Miner/validator emit Prometheus metrics or structured logs
      Key metrics: ingest_rate, query_latency_p99, proof_success_rate, score

---

## PHASE 7 — Mainnet Launch
> TAO incentives flowing, real miners competing

### Mainnet Burn Cost Reality
The mainnet subnet registration burn is **dynamic and expensive** (~15,000–20,000 TAO, ~$6–10M at current prices).
You do NOT pay this out of pocket. The realistic path:

| Route | How |
|-------|-----|
| **OTF Grant** | Apply to Opentensor Foundation — they fund strong subnets with demonstrated testnet traction |
| **Validator investment** | Validators want to stake on profitable subnets — they may co-fund the burn in exchange for early validator access |
| **Community fundraise** | If testnet metrics are strong, the community pays the burn collectively |

**Action:** Build testnet presence first → apply for OTF grant → burn covered.

---

### How You Make Money (Subnet Owner Economics)

Bittensor routes **18% of all subnet emissions directly to the subnet owner's coldkey**.
This is automatic, on-chain, no action required once registered on mainnet.

**Emissions math:**
- Total Bittensor emissions: ~7,200 TAO/day across all ~64 subnets
- Each subnet earns a share based on root validator weights (how much the network values your subnet)
- Owner cut = 18% of your subnet's share, paid to your coldkey every block

**Conservative projection for Engram (once on mainnet):**

| Scenario | Subnet share | Daily subnet TAO | Your 18% cut | At $450/TAO |
|----------|-------------|-----------------|--------------|-------------|
| Launch (small) | 0.2% | 14 TAO/day | 2.5 TAO/day | ~$1,100/day |
| Growing | 0.5% | 36 TAO/day | 6.5 TAO/day | ~$2,900/day |
| Established | 1.5% | 108 TAO/day | 19 TAO/day | ~$8,600/day |
| Top-tier subnet | 3% | 216 TAO/day | 39 TAO/day | ~$17,500/day |

These are **passive income** — automatically deposited to your wallet every ~12 seconds.

**Additional revenue streams:**
- Run your own validator on Engram (earn from the 41% validator pool on top of owner cut)
- SDK/API access tier for enterprise users querying the network
- Future: protocol fee on ingest transactions (governance vote)

**What drives your subnet share higher:**
- More miners → better query latency and recall scores
- Stronger validators doing accurate scoring
- Real usage (ingest + query volume)
- Root validators allocating more weight to Engram as it proves utility

---

- [ ] **7.1** Apply for OTF grant
      Opentensor Foundation grants program — submit after testnet is live with metrics
      Include: GitHub, demo video, miner count, query volume stats

- [ ] **7.2** Mainnet subnet registration
      Fund burn via grant/validators. Register with `SUBTENSOR_NETWORK=finney`
      Coldkey used for registration = coldkey that receives 18% owner emissions forever

- [ ] **7.3** Subnet metadata on-chain
      Set subnet name, description, GitHub link via `btcli`

- [ ] **7.4** Whitepaper / documentation site
      Public docs: subnet design, miner setup, validator setup, SDK usage
      Required for OTF grant application and miner recruitment

- [ ] **7.5** Miner onboarding guide
      Step-by-step: hardware requirements, setup, registration, running
      Target: 10+ external miners in first 2 weeks

- [ ] **7.6** Emissions flowing
      Validator setting weights, miners earning TAO, owner cut hitting coldkey
      Monitor via taostats.io → track your subnet's emission share over time

- [ ] **7.7** Run your own validator on Engram
      Stack validator rewards on top of owner cut
      Validator pool = 41% of subnet emissions

---

## Current Status

| Phase | Status |
|-------|--------|
| 0 — Local Chain | COMPLETE ✓ |
| 1 — Neurons E2E | PENDING |
| 2 — DHT/Replication | PENDING |
| 3 — SDK/DX | PARTIAL (CLI done) |
| 4 — Testnet | BLOCKED (need TAO) |
| 5 — Rust Core | PARTIAL (code done, not integrated) |
| 6 — Production | PENDING |
| 7 — Mainnet | PENDING |

---

## Build Progress Log

| Date | Event |
|------|-------|
| 2026-04-02 | engram-core Rust crate: CID + proof, 9 tests passing |
| 2026-04-02 | Python neurons: miner + validator complete |
| 2026-04-02 | FAISS metadata persistence fix (cross-process queries) |
| 2026-04-02 | DHT routing layer + replication manager: 55 tests passing |
| 2026-04-02 | CLI (engram ingest/query/status/demo) shipped |
| 2026-04-02 | local subtensor build started (Rust 1.89 toolchain) |
| 2026-04-03 | storage/__init__.py wired, register_local_subnet.py added |
| 2026-04-03 | subtensor build in progress (~40 min, polkadot-sdk checkout) |

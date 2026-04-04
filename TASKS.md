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

- [x] **1.1** Start miner neuron
      aiohttp JSON server live on 0.0.0.0:8091 ✓

- [x] **1.2** Start validator neuron
      Queries miner, recall_scores={0: 1.0}, weights set on chain ✓

- [x] **1.3** Ingest vectors via CLI
      10 ground-truth vectors seeded, CIDs match exactly ✓

- [x] **1.4** Query vectors via CLI
      QuerySynapse returns top-K results with correct CIDs ✓

- [x] **1.5** Storage proofs working
      Challenge PASSED | miner=0 | rate=1.00 ✓

- [x] **1.6** Weight-setting on chain
      Weights set successfully every 600s ✓

- [x] **1.7** Full scoring loop verified
      demo score=0.938 (recall=0.875, latency=1.0, proof=1.0) ✓

---

## PHASE 2 — DHT & Replication Wired into Neurons
> CID routing and replication across multiple miners

- [x] **2.1** Wire DHTRouter into miner neuron
      On startup: `router.sync_from_metagraph(metagraph.axons, metagraph.uids.tolist())`
      On IngestSynapse: check `router.should_store(cid)` before storing

- [x] **2.2** Wire ReplicationManager into miner
      On successful ingest: `replication_mgr.register(cid, assigned_uids)`
      Validator confirm/unconfirm after each challenge result

- [x] **2.3** Sync metagraph periodically
      Miner + validator refresh metagraph + DHT every 60s / each loop cycle

- [x] **2.4** Multi-miner local test
      Spin up 2 miners on different ports
      Ingest CID → verify it lands on both assigned miners via DHT ✓

- [x] **2.5** Repair targeting
      Kill one miner → `replication_mgr.handle_miner_offline(uid)`
      Validator detects `ReplicationStatus.DEGRADED` and triggers repair ✓
      8/8 checks passing (test_repair_targeting.py)

---

## PHASE 3 — SDK & Developer Experience
> External devs can use Engram programmatically

- [x] **3.1** SDK client tested against live local neurons
      `from engram.sdk import EngramClient`
      `client.ingest("text")`, `client.query("query")` round-trip ✓
      28/28 checks passing (test_sdk.py)

- [x] **3.2** SDK error handling
      Timeouts, miner offline, bad CID — all handled gracefully with clear exceptions ✓
      MinerOfflineError, IngestError, QueryError, InvalidCIDError all raised correctly

- [x] **3.3** JSONL batch ingest
      `client.batch_ingest_file("./data/corpus.jsonl")` ✓
      64 rec/sec on 50-record batch; error tolerance (bad records skipped)
      13/13 checks passing (test_batch_ingest.py)

- [x] **3.4** CLI `engram status` shows live neuron info ✓
      `engram status --live`: connects to metagraph, shows UID/hotkey/IP/stake/health
      "← you" label on own hotkey; offline detection via health probe

- [x] **3.5** PyPI package prep ✓
      `pyproject.toml`: classifiers, URLs, optional deps (qdrant, openai, dev)
      `pip install -e .` installs CLI + SDK; `engram --help` works
      Entry point: `engram = "engram.cli:app"`

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

- [x] **5.1** Build engram-core wheel ✓
      `cd engram-core && maturin develop --release` → 2s build
      `import engram_core; engram_core.generate_cid(...)` works

- [x] **5.2** Rust CID wired into ingest.py ✓
      `ingest.py`: tries `engram_core.generate_cid()` first, falls back to Python
      Cross-validated: Rust and Python produce identical CIDs
      Note: FFI overhead (list conversion) means Python hashlib path faster for single CIDs;
      Rust is the canonical spec, Python stays as fallback

- [x] **5.3** Rust proof verification wired into challenge.py ✓
      `challenge.py`: `engram_core.generate_challenge/response/verify_response`
      Full challenge round-trip verified

- [x] **5.4** Rust unit tests passing ✓
      `cargo test --no-default-features` → 9/9 green

- [x] **5.5** CI pipeline updated ✓
      GitHub Actions: `pytest` (55 tests) + `cargo test` (9 tests) + wheel build smoke test

---

## PHASE 6 — Production Hardening
> Ready for mainnet miners to join

- [x] **6.1** Qdrant production setup
      Docker Qdrant running, `VECTOR_STORE_BACKEND=qdrant` working
      Fixed qdrant-client v1.17.1 API (`query_points` replacing removed `.search()`) ✓

- [x] **6.2** Validator ground truth dataset
      1000 entries in `data/ground_truth.jsonl` — generated via `scripts/generate_ground_truth.py` ✓

- [x] **6.3** Anti-spam stake check
      `MIN_INGEST_STAKE_TAO=0.001` — wired into `IngestHandler._check_stake()`, fails open ✓

- [x] **6.4** Rate limiting
      `RateLimiter` sliding window per hotkey (100 req/60s), HTTP 429 on breach ✓

- [x] **6.5** Miner incentive documentation
      Full miner guide in `docs/miner.md` + README updated ✓

- [x] **6.6** Monitoring
      Prometheus metrics at `GET /metrics` — 9 metrics (ingest/query counters, histograms,
      proof_success_rate, vectors_stored, peers_online, score) ✓

---

## PHASE 8 — Normal User Experience
> Make Engram useful to everyday Bittensor users (not just miners/validators)

- [x] **8.1** Wallet pattern tracker
      `WalletTracker` persists per-hotkey ingest/query counts + CID history to JSON
      Miner wires tracker into handle_ingest + handle_query
      `GET /wallet-stats` + `GET /wallet-stats/{hotkey}` endpoints on miner + FastAPI
      `engram wallet-stats [hotkey] [--live] [--netuid]` CLI command ✓

- [x] **8.2** Subnet analytics dashboard (web)
      engram-web dashboard: live stats, miner leaderboard, query playground
      FastAPI backend (`/stats`, `/miners`, `/query`, `/ingest`) proxied via Next.js rewrites ✓

- [x] **8.3** AI agent memory UX
      `engram/sdk/langchain.py` — EngramVectorStore (LangChain adapter)
        add_texts, add_documents, similarity_search, similarity_search_with_score,
        from_texts classmethod, as_retriever(), health()
      `engram/sdk/llama_index.py` — EngramVectorStore (LlamaIndex adapter)
        add, delete (no-op), query, from_documents classmethod
      `scripts/demo_agent_memory.py` — full demo of all 3 patterns ✓

- [x] **8.4** "Store my data" onboarding flow (web)
      `IngestForm` component on dashboard: paste text → Store → get CID with copy button ✓
      Backend: `POST /api/subnet/ingest` added to FastAPI ✓

- [x] **8.5** Personal knowledge base demo
      `engram ingest --dir ./notes` — recursively ingests .txt / .md / .jsonl files ✓

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

- [x] **7.4** Whitepaper / documentation site
      `docs/` — architecture, miner, validator, SDK, CLI, protocol (6 files, 1500+ lines) ✓
      Required for OTF grant application and miner recruitment

- [x] **7.5** Miner onboarding guide
      `docs/miner.md` — full setup, config, optimisation, monitoring, troubleshooting ✓
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
| 1 — Neurons E2E | COMPLETE ✓ (score=0.938) |
| 2 — DHT/Replication | COMPLETE ✓ (multi-miner + repair targeting verified) |
| 3 — SDK/DX | COMPLETE ✓ (SDK, batch ingest, status --live, PyPI ready) |
| 4 — Testnet | BLOCKED (need TAO) |
| 5 — Rust Core | COMPLETE ✓ (wheel built, wired into neurons, 9/9 tests, CI) |
| 6 — Production | COMPLETE ✓ (Qdrant, ground truth, anti-spam, rate limit, metrics, docs) |
| 7 — Mainnet | PENDING (blocked on testnet TAO) |
| 8 — Normal User UX | COMPLETE ✓ (all 5 tasks done) |

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
| 2026-04-03 | miner: switched to aiohttp JSON server (matches validator direct HTTP) |
| 2026-04-03 | miner: fixed challenge handler — now uses validator's nonce for HMAC proof |
| 2026-04-03 | miner: DHT + ReplicationManager wired in (2.1, 2.2, 2.3) |
| 2026-04-03 | validator: DHT sync + replication confirm/unconfirm after challenges |
| 2026-04-03 | all 55 tests passing |
| 2026-04-04 | Python CID separator bug fixed (json separators=(',',':') to match Rust serde_json) |
| 2026-04-04 | validator: urllib thread-pool replaces aiohttp (fixes nest_asyncio/TimerContext conflict) |
| 2026-04-04 | PHASE 1 COMPLETE: miner + validator running, recall=1.0, proof_rate=1.0, demo score=0.938 |
| 2026-04-04 | Phase 2.4: multi-miner DHT test PASS (2 miners, CID ingested+queried on both) |
| 2026-04-04 | Phase 2.5: repair targeting 8/8 PASS (offline detection, DEGRADED status, repair routing) |
| 2026-04-04 | PHASE 2 COMPLETE: DHT + replication fully verified |
| 2026-04-04 | Phase 3.1/3.2: EngramClient SDK 28/28 tests passing (ingest, query, error handling) |
| 2026-04-04 | Phase 3.3: JSONL batch ingest 13/13 PASS — 64 rec/sec, error tolerance working |
| 2026-04-04 | Phase 3.4: engram status --live shows metagraph neurons, stake, health probes |
| 2026-04-04 | Phase 3.5: pyproject.toml finalized, pip install -e . works, engram CLI ready |
| 2026-04-04 | PHASE 3 COMPLETE: SDK + CLI fully working |
| 2026-04-04 | Phase 5: engram-core wheel built (2s), 9/9 Rust tests, CID parity verified |
| 2026-04-04 | Phase 5: CI updated — pytest (55) + cargo test (9) + wheel smoke test |
| 2026-04-04 | PHASE 5 COMPLETE: Rust core integrated |
| 2026-04-04 | Qdrant Docker running, fixed for qdrant-client v1.17.1 |
| 2026-04-04 | Anti-spam stake check + per-hotkey rate limiter (100 req/60s, HTTP 429) |
| 2026-04-04 | Prometheus metrics endpoint (9 metrics, GET /metrics) |
| 2026-04-04 | Ground truth dataset generated: 1000 entries, 74 texts/sec (MPS) |
| 2026-04-04 | PHASE 6 COMPLETE: production hardening done |
| 2026-04-04 | Full docs: architecture, miner, validator, SDK, CLI, protocol (6 files) |
| 2026-04-04 | Phase 8.4: IngestForm on dashboard + FastAPI POST /ingest |
| 2026-04-04 | Phase 8.5: engram ingest --dir (recursive .txt/.md/.jsonl) |
| 2026-04-04 | Phase 8.1: WalletTracker + engram wallet-stats CLI + /wallet-stats endpoints |
| 2026-04-04 | Phase 8.3: LangChain + LlamaIndex VectorStore adapters + agent memory demo |
| 2026-04-04 | PHASE 8 COMPLETE: all Normal User UX tasks done |

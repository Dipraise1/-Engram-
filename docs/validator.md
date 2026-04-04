# Running a Validator

Validators score miners, issue storage proof challenges, and set on-chain weights to distribute TAO emissions.

---

## Requirements

| Resource | Minimum |
|----------|---------|
| CPU | 2 vCPU |
| RAM | 4 GB |
| Python | 3.10+ |
| TAO stake | Enough to be in the top 64 validators (varies by subnet) |

The validator does **not** need a vector store or Qdrant.

---

## Installation

```bash
git clone https://github.com/Dipraise1/-Engram-.git
cd Engram
pip install -e ".[dev]"
cd engram-core && maturin develop --release && cd ..
```

---

## Ground Truth Dataset

The validator needs a ground truth dataset to evaluate miner recall. Generate one:

```bash
USE_LOCAL_EMBEDDER=true python scripts/generate_ground_truth.py --count 1000
```

This creates `data/ground_truth.jsonl` — 1000 entries, each with:
- `text`: the original text
- `embedding`: float32 vector
- `cid`: content identifier
- `top_k_cids`: expected top-10 closest CIDs by cosine similarity

The default path can be overridden with `GROUND_TRUTH_PATH=./data/ground_truth.jsonl`.

---

## Configuration

```bash
# .env — Validator configuration

# Bittensor identity
WALLET_NAME=default
WALLET_HOTKEY=validator
SUBTENSOR_NETWORK=finney
NETUID=<subnet-uid>

# Ground truth
GROUND_TRUTH_PATH=./data/ground_truth.jsonl

# Logging
LOG_LEVEL=INFO
```

---

## Running

```bash
python neurons/validator.py
```

Startup log:

```
INFO  Engram Validator v0.1.0 | network=finney | netuid=42
INFO  Ground truth entries: 1000
INFO  DHT ready | peers=15
```

---

## Scoring Loop

The validator runs three independent timers:

### Scoring round (every 120 seconds)

1. Sample 5 random entries from the ground truth dataset
2. Send each entry's `embedding` as a `QuerySynapse` to every registered miner
3. Compare the returned CIDs against each entry's `top_k_cids`
4. Record `recall@10` and query latency per miner

### Challenge round (every 300 seconds)

1. Pick a random CID from the ground truth
2. Build a challenge: `{cid, nonce_hex (32 bytes), expires_at (now + 30s)}`
3. Send `ChallengeSynapse` to every registered miner
4. Verify each response using the Rust `verify_response` function
5. Record pass/fail per miner; update the replication manager

### Weight round (every 600 seconds)

1. Compute composite score per miner:
   ```
   score = 0.50 × recall@10  +  0.30 × latency_score  +  0.20 × proof_rate
   ```
2. Normalise scores so they sum to 1.0
3. Call `subtensor.set_weights(netuid, uids, weights)`

---

## Scoring Reference

### recall@10

```python
hits = len(set(returned[:10]) & set(ground_truth[:10]))
recall = hits / min(10, len(ground_truth))
```

A miner that returns all 10 expected CIDs scores 1.0. A miner that returns 7 scores 0.7.

### latency_score

```python
if latency_ms <= 100:   return 1.0
if latency_ms >= 500:   return 0.0
return 1.0 − (latency_ms − 100) / 400
```

### proof_success_rate

Rolling fraction of storage challenges that the miner passed:

```
proof_rate = passed_challenges / total_challenges
```

### Composite score weights

| Component | Weight | Config constant |
|-----------|--------|-----------------|
| recall@10 | 0.50 | `SCORE_ALPHA` |
| latency | 0.30 | `SCORE_BETA` |
| proof rate | 0.20 | `SCORE_GAMMA` |

Weights are defined in `engram/config.py` and apply subnet-wide.

---

## Slashing

Miners with `proof_success_rate < SLASH_THRESHOLD` (default 0.50) receive a composite score of 0 regardless of recall and latency. This prevents miners from gaming recall/latency while actually discarding stored data.

---

## systemd Service

```ini
# /etc/systemd/system/engram-validator.service
[Unit]
Description=Engram Validator
After=network.target

[Service]
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env
ExecStart=/opt/engram/.venv/bin/python neurons/validator.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now engram-validator
```

---

## Troubleshooting

**Weight setting fails with `StakeError`**
- Ensure your validator hotkey has enough stake to be active in the subnet.

**All miners score 0 on recall**
- Check that the ground truth CIDs match what miners have stored (validators should pre-seed miners with the ground truth corpus on mainnet launch).
- Verify miners are reachable: `engram status --live --netuid <uid>`

**Challenge round: all proofs failing**
- The miner must have ingested the challenged CID before the challenge is issued. On a fresh subnet, run `scripts/seed_corpus.py` against all miners to populate initial data.

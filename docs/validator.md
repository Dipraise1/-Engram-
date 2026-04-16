# Running a Validator

Validators score miners, issue storage proof challenges, and set on-chain weights to distribute TAO emissions.

---

## Requirements

| Resource | Minimum |
|----------|---------|
| CPU | 2 vCPU |
| RAM | 2 GB |
| Python | 3.10+ |
| TAO stake | Enough to be in the active validator set |

The validator does **not** need a vector store or Qdrant.

---

## Installation

```bash
git clone https://github.com/Dipraise1/-Engram-.git
cd -Engram-
pip install -e .
cd engram-core && maturin develop --release && cd ..
```

---

## Ground Truth Dataset

The validator needs a ground truth dataset to evaluate miner recall. Generate one:

```bash
USE_LOCAL_EMBEDDER=true python scripts/generate_ground_truth.py --count 1000
```

This creates `data/ground_truth.jsonl` — entries each with:
- `text`: the original text
- `embedding`: float32 vector (384d)
- `cid`: content identifier
- `top_k_cids`: expected top-10 closest CIDs by cosine similarity

---

## Configuration

```bash
cp .env.example .env.validator
```

```bash
# .env.validator

# Bittensor identity
WALLET_NAME=engram
WALLET_HOTKEY=validator
SUBTENSOR_NETWORK=test       # or ws endpoint
NETUID=450

# Ground truth
GROUND_TRUTH_PATH=./data/ground_truth.jsonl

# Miner connectivity
MINER_PORT=8091              # fallback when metagraph axon.port is 0
MINER_IP=127.0.0.1          # fallback for local dev only

# Logging
LOG_LEVEL=INFO
```

---

## Running

```bash
ENV_FILE=.env.validator python neurons/validator.py
```

Startup log:

```
INFO  Engram Validator v0.1.2 | network=test | netuid=450
INFO  Ground truth entries: 15
INFO  Replication: loaded 1009 records from DB
```

Like the miner, the validator retries the subtensor connection up to 5 times on startup and reconnects automatically if the chain drops mid-loop. It will not crash on a flaky testnet RPC.

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
MemoryMax=600M

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now engram-validator
journalctl -u engram-validator -f
```

---

## Scoring Loop

### Scoring round (every 120 seconds)

1. Sample 5 random entries from the ground truth dataset
2. Send each entry's embedding as a `QuerySynapse` to every registered miner
3. Compare returned CIDs against the entry's `top_k_cids`
4. Record `recall@10` and query latency per miner

### Challenge round (every 300 seconds)

1. Pick a random CID from the ground truth
2. Build a challenge: `{cid, nonce_hex (32 bytes), expires_at (now + 30s)}`
3. Send `ChallengeSynapse` to every registered miner
4. Verify each response with the Rust `verify_response` function
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

### latency_score

```python
if latency_ms <= 100:   return 1.0
if latency_ms >= 500:   return 0.0
return 1.0 - (latency_ms - 100) / 400
```

### proof_success_rate

Rolling fraction of storage challenges the miner passed:

```
proof_rate = passed_challenges / total_challenges
```

### Slashing

Miners with `proof_success_rate < 0.50` receive composite score 0 regardless of recall and latency.

---

## Troubleshooting

**`avg_score: null` on dashboard**
- The validator needs ~600s of uptime to complete its first weight-setting round.
- Check `journalctl -u engram-validator -n 50` for scoring round activity.

**`SubstrateRequestException: Internal error`**
- Testnet RPC flakiness — the validator retries automatically. Not a bug.

**All miners score 0 on recall**
- Verify miners have been seeded: `python scripts/seed_miner_ground_truth.py`
- Check miners are reachable: `curl http://<miner-ip>:8091/health`

**Challenge round: all proofs failing**
- The miner must have the challenged CID stored before the challenge is issued.
- Seed all miners with ground truth data before expecting passing challenges.

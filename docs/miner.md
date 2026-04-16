# Running a Miner

This guide covers everything needed to run an Engram miner on testnet (subnet 450).

---

## Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 vCPU | 4+ vCPU |
| RAM | 2 GB | 4 GB |
| Disk | 20 GB SSD | 100 GB NVMe |
| Python | 3.10+ | 3.11+ |
| OS | Linux/macOS | Ubuntu 22.04 |
| Network | Static IP | Static IP |

---

## Installation

### 1. Clone and install

```bash
git clone https://github.com/Dipraise1/-Engram-.git
cd -Engram-
pip install -e .
```

### 2. Build the Rust core (optional but recommended)

```bash
pip install maturin
cd engram-core && maturin develop --release && cd ..
```

The Rust wheel adds faster CID generation and is used for storage proof verification. The miner falls back to pure Python if not built.

### 3. Register your hotkey

```bash
btcli wallet new_coldkey --wallet.name engram
btcli wallet new_hotkey --wallet.name engram --wallet.hotkey miner

# Testnet
btcli subnet register --netuid 450 --wallet.name engram --wallet.hotkey miner --subtensor.network test
```

---

## Configuration

```bash
cp .env.example .env.miner
```

```bash
# .env.miner

# Bittensor identity
WALLET_NAME=engram
WALLET_HOTKEY=miner
SUBTENSOR_NETWORK=test       # or ws endpoint, e.g. wss://test.finney.opentensor.ai
NETUID=450

# Network
MINER_PORT=8091
EXTERNAL_IP=<your-public-ip>   # must be routable from validators

# Embedder — all-MiniLM-L6-v2 runs locally, no API key needed
USE_LOCAL_EMBEDDER=true

# Logging
LOG_LEVEL=INFO
```

---

## Running

```bash
ENV_FILE=.env.miner python neurons/miner.py
```

Startup log on a healthy connection:

```
INFO  Engram Miner v0.1.2 | network=test | netuid=450
INFO  Subtensor connected
INFO  Vector store ready | 1019 vectors
INFO  DHT ready | peers=7 | uid=2
INFO  Axon registered | 72.62.2.34:8091
INFO  Miner HTTP server live on 0.0.0.0:8091
```

If the testnet RPC is temporarily unavailable the miner logs retries and starts chain-less:

```
WARNING  Subtensor connect failed (attempt 1/5): Internal error — retrying in 10s
...
WARNING  Could not connect to subtensor after 5 attempts — running chain-less
INFO  Miner HTTP server live on 0.0.0.0:8091
```

It will reconnect and register on-chain as soon as the RPC becomes available.

Verify it is running:

```bash
curl http://localhost:8091/health
# {"status": "ok", "vectors": 1019, "uid": 2}
```

---

## systemd Service

```ini
# /etc/systemd/system/engram-miner.service
[Unit]
Description=Engram Miner
After=network.target

[Service]
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env
ExecStart=/opt/engram/.venv/bin/python neurons/miner.py
Restart=always
RestartSec=10
MemoryMax=2G
MemoryHigh=1700M

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now engram-miner
journalctl -u engram-miner -f
```

---

## Maximising Your Score

```
score = 0.50 × recall@10  +  0.30 × latency_score  +  0.20 × proof_success_rate
```

### Recall@10 (50%)

- Never delete stored vectors — every CID is a potential query target.
- Seed the miner with ground truth data so it has content to recall:
  ```bash
  python scripts/seed_miner_ground_truth.py --miner-url http://YOUR_IP:8091
  ```

### Latency (30%)

- Target ≤100ms per query (1.0 score). Above 500ms scores 0.
- Keep the miner on a low-latency server with ≥2 cores.

### Proof Rate (20%)

- The miner must respond to HMAC challenges for stored CIDs within the TTL (~30s).
- Ensure `EXTERNAL_IP` is correct and port `8091` is open in your firewall.
- Keep system clock synced (NTP) — challenges expire by Unix timestamp.

---

## Monitoring

```bash
curl http://localhost:8091/stats
```

```json
{
  "status": "ok",
  "vectors": 1019,
  "peers": 7,
  "uid": 2,
  "queries_today": 5,
  "p50_latency_ms": 2.5,
  "proof_rate": 0.93,
  "uptime_pct": 99.9,
  "block": 6922655,
  "avg_score": 0.76
}
```

---

## Troubleshooting

**Validators can't reach the miner**
- Check `EXTERNAL_IP` is your public IP (not `127.0.0.1`)
- Verify port 8091 is open: `nc -zv <your-ip> 8091`

**`SubstrateRequestException: Internal error` on startup**
- This is a testnet RPC issue, not a bug. The miner retries automatically and starts chain-less. It will self-heal once the RPC recovers.

**Recall score is 0**
- Seed ground truth data if the miner is freshly started.
- Check that the FAISS index has vectors: `curl http://localhost:8091/stats` → `vectors > 0`.

**Proof challenges failing**
- Check miner logs for `Challenge error:` messages.
- Ensure system clock is synced (`timedatectl status`).

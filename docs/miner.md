# Running a Miner

This guide covers everything needed to run an Engram miner on testnet or mainnet.

---

## Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 vCPU | 4+ vCPU |
| RAM | 4 GB | 16 GB |
| Disk | 20 GB SSD | 100 GB NVMe SSD |
| Python | 3.10+ | 3.11+ |
| OS | Linux/macOS | Ubuntu 22.04 |
| Network | Static IP or DDNS | Static IP |

---

## Installation

### 1. Clone and install

```bash
git clone https://github.com/Dipraise1/-Engram-.git
cd Engram
pip install -e ".[qdrant]"
```

### 2. Build the Rust core

```bash
pip install maturin
cd engram-core && maturin develop --release && cd ..
```

The Rust wheel adds ~10% faster CID generation and is required for storage proof verification. The miner falls back to pure Python if not built.

### 3. Start Qdrant

```bash
docker run -d --name qdrant -p 6333:6333 -v $(pwd)/data/qdrant:/qdrant/storage qdrant/qdrant
```

Or with docker-compose:

```bash
docker compose up -d qdrant
```

### 4. Register your hotkey

You need a Bittensor wallet with enough TAO to register on the subnet:

```bash
btcli subnet register --netuid <NETUID> --wallet.name <name> --wallet.hotkey <hotkey>
```

---

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

```bash
# .env — Miner configuration

# Bittensor identity
WALLET_NAME=default
WALLET_HOTKEY=default
SUBTENSOR_NETWORK=finney          # or ws://127.0.0.1:9944 for local
NETUID=<subnet-uid>

# Network
MINER_PORT=8091
EXTERNAL_IP=<your-public-ip>      # must be reachable from validators

# Vector store
VECTOR_STORE_BACKEND=qdrant       # or faiss
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=engram

# Embedder
USE_LOCAL_EMBEDDER=false          # true = offline sentence-transformers
OPENAI_API_KEY=sk-...             # required if USE_LOCAL_EMBEDDER=false

# Rate limiting
RATE_LIMIT_MAX_REQUESTS=100       # max ingest requests per window
RATE_LIMIT_WINDOW_SECS=60

# Logging
LOG_LEVEL=INFO
```

---

## Running

```bash
python neurons/miner.py
```

The miner logs its startup sequence:

```
INFO  Engram Miner v0.1.0 | network=finney | netuid=42
INFO  Wallet: 5FHGPfix...
INFO  Vector store: qdrant | 0 vectors loaded
INFO  DHT ready | peers=12 | uid=7
INFO  Miner HTTP server live on 0.0.0.0:8091
INFO  Axon registered on-chain | 1.2.3.4:8091
```

Verify it's running:

```bash
curl http://localhost:8091/health
# {"status": "ok", "vectors": 0, "uid": 7, "peers": 12}
```

---

## Keeping the Miner Online

Use a process manager so the miner restarts automatically:

**systemd** (recommended for Linux):

```ini
# /etc/systemd/system/engram-miner.service
[Unit]
Description=Engram Miner
After=network.target docker.service
Requires=docker.service

[Service]
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env
ExecStart=/opt/engram/.venv/bin/python neurons/miner.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now engram-miner
journalctl -u engram-miner -f
```

**PM2** (alternative):

```bash
pm2 start "python neurons/miner.py" --name engram-miner --cwd /opt/engram
pm2 save && pm2 startup
```

---

## Maximising Your Score

Your composite score is:

```
score = 0.50 × recall@10  +  0.30 × latency_score  +  0.20 × proof_success_rate
```

### Recall@10 (50% of score)

Recall is the most impactful component. The validator embeds known texts and checks how many of the expected CIDs appear in your top-10 results.

- **Use Qdrant** (`VECTOR_STORE_BACKEND=qdrant`). FAISS HNSW can miss recently added nodes in small growing indices, silently degrading recall to 0 for fresh data.
- Keep `HNSW_EF_SEARCH` ≥ 64 (default). Higher values improve recall at the cost of latency.
- **Never delete stored vectors** — every CID is a potential query target. Pruning or evicting data causes recall to drop to 0 for those entries.

### Latency Score (30% of score)

The latency score is linear between your target (100ms → 1.0) and baseline (500ms → 0.0):

```
latency_score = max(0, 1 − (latency_ms − 100) / 400)
```

- Run Qdrant on the **same machine** as the miner to avoid network RTT.
- Use ≥4 CPU cores — Qdrant's HNSW search is CPU-bound.
- If using local embedder, MPS (Apple Silicon) or CUDA reduces embed time by ~3×.
- Avoid running other CPU-heavy workloads on the same machine.

### Proof Success Rate (20% of score)

The validator issues HMAC challenge-response challenges for CIDs it has ingested. The miner must:
1. Have the CID stored (never delete data)
2. Respond within the TTL (typically ~30s)
3. Compute the correct HMAC

- Make sure `EXTERNAL_IP` is set correctly and the port is open in your firewall.
- Ensure the miner process doesn't stall on GC, disk I/O, or embedder startup.

---

## Monitoring

The miner exposes Prometheus metrics at `GET /metrics`. Scrape with Prometheus or view directly:

```bash
curl http://localhost:8091/metrics
```

Key metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `engram_vectors_stored` | Gauge | Total vectors in the store |
| `engram_ingest_total{status}` | Counter | Ingest requests by status (`ok`, `error`, `rate_limited`, `low_stake`) |
| `engram_ingest_duration_ms` | Histogram | Ingest latency distribution |
| `engram_query_total{status}` | Counter | Query requests by status |
| `engram_query_duration_ms` | Histogram | Query latency distribution |
| `engram_proof_total{result}` | Counter | Challenge results (`pass`, `fail`, `expired`) |
| `engram_proof_success_rate` | Gauge | Rolling proof pass rate (0–1) |
| `engram_score` | Gauge | Last composite score from validator |
| `engram_peers_online` | Gauge | DHT peer count |

**Prometheus scrape config:**

```yaml
scrape_configs:
  - job_name: engram-miner
    static_configs:
      - targets: ['localhost:8091']
    metrics_path: /metrics
```

---

## Running a Second Miner

For local testing or running a standby miner, use a separate `.env` file:

```bash
# .env.miner2
WALLET_HOTKEY=hotkey2
MINER_PORT=8093
FAISS_INDEX_PATH=./data/engram2.index
QDRANT_COLLECTION=engram2
```

```bash
env $(cat .env.miner2 | xargs) python neurons/miner.py
```

---

## Troubleshooting

**Miner starts but validators can't reach it**
- Check that `EXTERNAL_IP` is set to your public IP (not `127.0.0.1`)
- Verify port `8091` is open: `nc -zv <your-ip> 8091`
- Some providers (AWS, GCP) require a security group rule

**Recall score is 0**
- Switch to Qdrant: `VECTOR_STORE_BACKEND=qdrant`
- Check that Qdrant is running: `curl http://localhost:6333/healthz`
- Make sure the miner has ingested data before the validator scores it

**Proof challenges failing**
- Verify the miner is returning `embedding_hash` and `proof` in challenge responses
- Check the miner logs for `Challenge error:` messages
- Ensure system clock is synced (NTP) — challenges expire by Unix timestamp

**Out of memory with large Qdrant collection**
- Qdrant maps vectors to disk by default. For very large collections, increase RAM or use `on_disk_payload: true` in Qdrant config.

#!/usr/bin/env bash
# ── Engram VPS Setup ──────────────────────────────────────────────────────────
# Ubuntu 24.04 — installs all dependencies, clones repo, configures firewall.
# Run as root on a fresh box:
#   bash <(curl -fsSL https://raw.githubusercontent.com/Dipraise1/-Engram-/main/scripts/vps-setup.sh)
# Or upload and run:
#   scp scripts/vps-setup.sh root@72.62.2.34:~ && ssh root@72.62.2.34 "bash ~/vps-setup.sh"

set -euo pipefail

ENGRAM_DIR="/opt/engram"
ENGRAM_REPO="https://github.com/Dipraise1/-Engram-.git"
PYTHON="python3.11"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Engram VPS Setup — Ubuntu 24.04"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. System update ──────────────────────────────────────────────────────────
echo "[1/7] Updating system..."
apt-get update -qq && apt-get upgrade -y -qq
apt-get install -y -qq \
    git curl wget build-essential pkg-config libssl-dev \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    ufw tmux htop jq

# ── 2. Firewall ───────────────────────────────────────────────────────────────
echo "[2/7] Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp      # SSH
ufw allow 8091/tcp    # Miner HTTP
# ufw allow 443/tcp   # Uncomment when you add TLS via nginx
ufw --force enable
echo "Firewall rules:"
ufw status numbered

# ── 3. Clone repo ─────────────────────────────────────────────────────────────
echo "[3/7] Cloning Engram..."
if [ -d "$ENGRAM_DIR" ]; then
    echo "  $ENGRAM_DIR exists — pulling latest..."
    git -C "$ENGRAM_DIR" pull
else
    git clone "$ENGRAM_REPO" "$ENGRAM_DIR"
fi
cd "$ENGRAM_DIR"

# ── 4. Python venv + deps ─────────────────────────────────────────────────────
echo "[4/7] Setting up Python environment..."
$PYTHON -m venv .venv
source .venv/bin/activate

pip install --upgrade pip -q
# Install engram-subnet + full node deps
pip install "engram-subnet[node]" -q
# Install remaining deps not in pypi package
pip install -r requirements.txt -q

echo "  Python deps installed."

# ── 5. Ground truth data ──────────────────────────────────────────────────────
echo "[5/7] Preparing data directory..."
mkdir -p data
if [ ! -f data/ground_truth.jsonl ]; then
    echo "  No ground_truth.jsonl found — validator will start with empty set."
    echo "  Run: source .venv/bin/activate && python scripts/generate_ground_truth.py"
fi

# ── 6. Systemd services ───────────────────────────────────────────────────────
echo "[6/7] Installing systemd services..."

cat > /etc/systemd/system/engram-miner.service << 'EOF'
[Unit]
Description=Engram Miner
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env.miner
ExecStart=/opt/engram/.venv/bin/python neurons/miner.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=engram-miner

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/engram-validator.service << 'EOF'
[Unit]
Description=Engram Validator
After=network-online.target engram-miner.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env.validator
ExecStart=/opt/engram/.venv/bin/python neurons/validator.py
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal
SyslogIdentifier=engram-validator

[Install]
WantedBy=multi-user.target
EOF

systemd-analyze verify /etc/systemd/system/engram-miner.service 2>/dev/null || true
systemd-analyze verify /etc/systemd/system/engram-validator.service 2>/dev/null || true
systemctl daemon-reload
echo "  Services installed (not started yet — configure .env files first)."

# ── 7. Env file templates ─────────────────────────────────────────────────────
echo "[7/7] Writing env templates..."

SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_PUBLIC_IP")

if [ ! -f .env.miner ]; then
    cat > .env.miner << ENVEOF
# Bittensor
WALLET_NAME=engram
WALLET_HOTKEY=miner
SUBTENSOR_NETWORK=test
NETUID=450

# Embedding (local, no API key needed)
USE_LOCAL_EMBEDDER=true
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384

# Vector store
VECTOR_STORE_BACKEND=faiss
FAISS_INDEX_PATH=/opt/engram/data/miner.index

# Network
MINER_PORT=8091
EXTERNAL_IP=${SERVER_IP}

# Rate limits
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECS=60

# Security (flip to true after validators are signing)
REQUIRE_HOTKEY_SIG=false
REQUIRE_METAGRAPH_REG=false

LOG_LEVEL=INFO
ENVEOF
    echo "  Created .env.miner (edit WALLET_NAME/WALLET_HOTKEY if different)"
else
    echo "  .env.miner already exists — skipping."
fi

if [ ! -f .env.validator ]; then
    cat > .env.validator << ENVEOF
# Bittensor
WALLET_NAME=engram
WALLET_HOTKEY=validator
SUBTENSOR_NETWORK=test
NETUID=450

# Embedding (must match miner)
USE_LOCAL_EMBEDDER=true
LOCAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384

# Ground truth
GROUND_TRUTH_PATH=/opt/engram/data/ground_truth.jsonl

# Scoring
SCORING_ALPHA=0.50
SCORING_BETA=0.30
SCORING_GAMMA=0.20
CHALLENGE_INTERVAL=300

# Transport (use http for now; switch to https after nginx TLS is up)
MINER_USE_HTTPS=false
VALIDATOR_TLS_VERIFY=true

LOG_LEVEL=INFO
ENVEOF
    echo "  Created .env.validator (edit WALLET_NAME/WALLET_HOTKEY if different)"
else
    echo "  .env.validator already exists — skipping."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Setup complete! Next steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo " 1. Create wallets:"
echo "    cd /opt/engram && source .venv/bin/activate"
echo "    btcli wallet create --wallet.name engram --wallet.hotkey miner"
echo "    btcli wallet create --wallet.name engram --wallet.hotkey validator"
echo ""
echo " 2. Get testnet TAO from faucet:"
echo "    https://discord.gg/bittensor  →  #faucet channel"
echo "    btcli wallet overview --wallet.name engram --subtensor.network test"
echo ""
echo " 3. Register on subnet 450:"
echo "    btcli subnet register --netuid 450 --wallet.name engram --wallet.hotkey miner --subtensor.network test"
echo "    btcli subnet register --netuid 450 --wallet.name engram --wallet.hotkey validator --subtensor.network test"
echo ""
echo " 4. Start services:"
echo "    systemctl enable --now engram-miner"
echo "    systemctl enable --now engram-validator"
echo ""
echo " 5. Watch logs:"
echo "    journalctl -u engram-miner -f"
echo "    journalctl -u engram-validator -f"
echo ""
echo " 6. Test miner is up:"
echo "    curl http://${SERVER_IP}:8091/health"
echo ""
echo " Server IP: ${SERVER_IP}"
echo " Miner URL: http://${SERVER_IP}:8091"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

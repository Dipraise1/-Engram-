#!/usr/bin/env bash
# Start miner 2 (port 8093) for multi-miner DHT testing.
# Miner 2 uses a separate FAISS index (./data/engram2.index) and the
# 'miner2' hotkey under the 'engram' wallet.
#
# Run from the project root:
#   bash scripts/start_miner2.sh

set -e
cd "$(dirname "$0")/.."

# Load miner2 env vars on top of defaults
export $(grep -v '^#' .env.miner2 | xargs)

echo "Starting Engram Miner 2"
echo "  Port:      $MINER_PORT"
echo "  Wallet:    $WALLET_NAME / $WALLET_HOTKEY"
echo "  Index:     $FAISS_INDEX_PATH"
echo "  Network:   $SUBTENSOR_ENDPOINT"
echo ""

.venv/bin/python -m neurons.miner

#!/usr/bin/env bash
# Stops and disables miner2/miner3, keeps just miner1 + validator.
# Run from local machine: bash scripts/reduce-to-one-miner.sh

VPS="root@72.62.2.34"

echo "==> Waiting for VPS..."
until ssh -o ConnectTimeout=5 -o BatchMode=yes "$VPS" true 2>/dev/null; do
    printf "."; sleep 5
done
echo " connected."

ssh "$VPS" bash << 'REMOTE'
set -euo pipefail

echo "[1/3] Stopping and disabling miner2 and miner3..."
systemctl stop engram-miner2 engram-miner3 2>/dev/null || true
systemctl disable engram-miner2 engram-miner3 2>/dev/null || true

echo "[2/3] Ensuring miner1 and validator are running..."
systemctl restart engram-miner
sleep 30
systemctl restart engram-validator

echo "[3/3] Status:"
systemctl is-active engram-miner engram-validator
free -h
ss -tlnp | grep -E '809[0-9]'
REMOTE

echo ""
echo "Done. Only miner1 (port 8091) + validator running."

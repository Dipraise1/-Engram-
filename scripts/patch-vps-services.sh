#!/usr/bin/env bash
# ── Patch live VPS systemd services ──────────────────────────────────────────
# Run from your local machine once the VPS is back up:
#   bash scripts/patch-vps-services.sh
#
# What this does:
#   1. Rewrites all 4 service files with memory limits + crash safety
#   2. Ensures ENV_FILE is set in .env.miner2 / .env.miner3
#   3. Opens firewall ports 8092 / 8093
#   4. Reloads systemd and restarts services with staggered timing

set -euo pipefail

VPS="root@72.62.2.34"

echo "==> Waiting for VPS to respond..."
until ssh -o ConnectTimeout=5 -o BatchMode=yes "$VPS" true 2>/dev/null; do
    printf "."
    sleep 5
done
echo " connected."

ssh "$VPS" bash << 'REMOTE'
set -euo pipefail

# ── 1. Harden service files ───────────────────────────────────────────────────

cat > /etc/systemd/system/engram-miner.service << 'EOF'
[Unit]
Description=Engram Miner
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
User=root
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env.miner
ExecStart=/opt/engram/.venv/bin/python neurons/miner.py
Restart=on-failure
RestartSec=30
TimeoutStartSec=120
MemoryMax=1100M
MemoryHigh=900M
OOMScoreAdjust=200
StandardOutput=journal
StandardError=journal
SyslogIdentifier=engram-miner

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/engram-miner2.service << 'EOF'
[Unit]
Description=Engram Miner 2
After=network-online.target engram-miner.service
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
User=root
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env.miner2
ExecStartPre=/bin/sleep 30
ExecStart=/opt/engram/.venv/bin/python neurons/miner.py
Restart=on-failure
RestartSec=30
TimeoutStartSec=150
MemoryMax=1100M
MemoryHigh=900M
OOMScoreAdjust=200
StandardOutput=journal
StandardError=journal
SyslogIdentifier=engram-miner2

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/engram-miner3.service << 'EOF'
[Unit]
Description=Engram Miner 3
After=network-online.target engram-miner.service engram-miner2.service
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
User=root
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env.miner3
ExecStartPre=/bin/sleep 60
ExecStart=/opt/engram/.venv/bin/python neurons/miner.py
Restart=on-failure
RestartSec=30
TimeoutStartSec=180
MemoryMax=1100M
MemoryHigh=900M
OOMScoreAdjust=200
StandardOutput=journal
StandardError=journal
SyslogIdentifier=engram-miner3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/engram-validator.service << 'EOF'
[Unit]
Description=Engram Validator
After=network-online.target engram-miner.service
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=3

[Service]
Type=simple
User=root
WorkingDirectory=/opt/engram
EnvironmentFile=/opt/engram/.env.validator
ExecStart=/opt/engram/.venv/bin/python neurons/validator.py
Restart=on-failure
RestartSec=30
TimeoutStartSec=120
MemoryMax=600M
MemoryHigh=500M
OOMScoreAdjust=100
StandardOutput=journal
StandardError=journal
SyslogIdentifier=engram-validator

[Install]
WantedBy=multi-user.target
EOF

echo "[1/4] Service files written."

# ── 2. Ensure ENV_FILE is set in miner2/3 env files ──────────────────────────

grep -q '^ENV_FILE=' /opt/engram/.env.miner2 \
    || echo 'ENV_FILE=/opt/engram/.env.miner2' >> /opt/engram/.env.miner2

grep -q '^ENV_FILE=' /opt/engram/.env.miner3 \
    || echo 'ENV_FILE=/opt/engram/.env.miner3' >> /opt/engram/.env.miner3

echo "[2/4] ENV_FILE entries verified in miner2/3 env files."

# ── 3. Open firewall ports ────────────────────────────────────────────────────

ufw allow 8092/tcp 2>/dev/null || true
ufw allow 8093/tcp 2>/dev/null || true
echo "[3/4] Firewall ports 8092/8093 open."

# ── 4. Reload and restart services staggered ─────────────────────────────────

systemctl daemon-reload

echo "[4/4] Restarting services (staggered)..."
systemctl restart engram-miner
echo "  miner started — waiting 45s before miner2..."
sleep 45
systemctl restart engram-miner2
echo "  miner2 started — waiting 45s before miner3..."
sleep 45
systemctl restart engram-miner3
echo "  miner3 started — waiting 20s before validator..."
sleep 20
systemctl restart engram-validator

echo ""
echo "==> All services restarted. Status:"
systemctl is-active engram-miner engram-miner2 engram-miner3 engram-validator
echo ""
echo "==> Listening ports:"
ss -tlnp | grep -E '809[0-9]' || echo "  (still starting — check again in 30s)"
REMOTE

echo ""
echo "Done. Run this to tail all logs:"
echo "  ssh $VPS 'journalctl -u engram-miner -u engram-miner2 -u engram-miner3 -f'"

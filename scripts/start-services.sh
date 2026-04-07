#!/usr/bin/env bash
set -euo pipefail

# ── Create systemd service files ──────────────────────────────────────────────
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

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/engram-validator.service << 'EOF'
[Unit]
Description=Engram Validator
After=network-online.target
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

[Install]
WantedBy=multi-user.target
EOF

# ── Ensure data dir exists ─────────────────────────────────────────────────────
mkdir -p /opt/engram/data

# ── Reload + enable + start ───────────────────────────────────────────────────
systemctl daemon-reload
systemctl enable --now engram-miner
systemctl enable --now engram-validator

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Services started!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
systemctl status engram-miner --no-pager -l | tail -20
echo ""
systemctl status engram-validator --no-pager -l | tail -20

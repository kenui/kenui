#!/usr/bin/env bash
# Installs the PAPER (fake money) trading bot as a 24/7 service on Ubuntu.
# No API keys, no real orders: it only reads public market data.
# Usage (as root on the server):
#   curl -fsSL https://raw.githubusercontent.com/kenui/kenui/claude/project-thread-yf5ysa/trader/deploy/install.sh | bash
set -euo pipefail
BRANCH="${BRANCH:-claude/project-thread-yf5ysa}"
DIR=/opt/kenui-trader

apt-get update -y && apt-get install -y git python3-venv python3-pip libgomp1
git ls-remote --exit-code --heads https://github.com/kenui/kenui.git "$BRANCH" >/dev/null 2>&1 || BRANCH=master   # branch merged and deleted -> use master
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch origin "$BRANCH" && git -C "$DIR" checkout -B "$BRANCH" FETCH_HEAD
else
  git clone --branch "$BRANCH" --depth 1 https://github.com/kenui/kenui.git "$DIR"
fi
cd "$DIR/trader"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

cat > /etc/systemd/system/kenui-paper.service <<UNIT
[Unit]
Description=Kenui paper trading bot (fake money)
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$DIR/trader
ExecStart=$DIR/trader/.venv/bin/python paper_bot.py
Restart=always
RestartSec=30
MemoryMax=3G

[Install]
WantedBy=multi-user.target
UNIT

echo "== self-test: one full cycle (takes 2-4 minutes the first time) =="
.venv/bin/python paper_bot.py --once 2>&1 | tail -n 8
systemctl daemon-reload
systemctl enable --now kenui-paper.service
sleep 3
systemctl --no-pager --lines=0 status kenui-paper.service | head -n 4
echo "== OK. Report any time with:  cd $DIR/trader && .venv/bin/python paper_bot.py --report =="

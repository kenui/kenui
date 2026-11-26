#!/usr/bin/env bash
# Installs the two PAPER (fake money) bots as 24/7 services on Ubuntu:
#   kenui-paper    the machine-learning dip buyer
#   kenui-listing  the listing short on a simulated prop-firm challenge
# No API keys, no real orders: it only reads public market data.
#
# Safe to run next to other software on the same server:
#   * everything lives in /opt/kenui-trader, in its own Python virtualenv (no global pip installs)
#   * runs as its own unprivileged user "kenuibot"
#   * opens NO network port; only makes outbound HTTPS requests to Binance
#   * hard limits: at most 50% of one CPU core and 1.5 GB of RAM, lowest CPU/disk priority
#   * system packages added only if missing: git, python3-venv, libgomp1 (nothing is upgraded or removed)
#   * remove everything with: bash /opt/kenui-trader/trader/deploy/uninstall.sh
#
# Usage (as root on the server):
#   curl -fsSL https://raw.githubusercontent.com/kenui/kenui/master/trader/deploy/install.sh | bash
set -euo pipefail
BRANCH="${BRANCH:-master}"
DIR=/opt/kenui-trader
BOTUSER=kenuibot

need=""
command -v git >/dev/null || need="$need git"
python3 -c "import venv, ensurepip" 2>/dev/null || need="$need python3-venv"
ldconfig -p | grep -q libgomp.so.1 || need="$need libgomp1"
if [ -n "$need" ]; then
  apt-get update -y && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-upgrade $need
fi

id "$BOTUSER" >/dev/null 2>&1 || useradd --system --home-dir "$DIR" --shell /usr/sbin/nologin "$BOTUSER"
git ls-remote --exit-code --heads https://github.com/kenui/kenui.git "$BRANCH" >/dev/null 2>&1 || BRANCH=master
if [ -d "$DIR/.git" ]; then
  git -c safe.directory="$DIR" -C "$DIR" fetch --depth 1 origin "$BRANCH" && git -c safe.directory="$DIR" -C "$DIR" checkout -q -f -B "$BRANCH" FETCH_HEAD
else
  git clone -q --branch "$BRANCH" --depth 1 https://github.com/kenui/kenui.git "$DIR"
fi
cd "$DIR/trader"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
mkdir -p data
chown -R "$BOTUSER":"$BOTUSER" "$DIR"

cat > /etc/systemd/system/kenui-paper.service <<UNIT
[Unit]
Description=Kenui paper trading bot (fake money, public data only)
After=network-online.target
Wants=network-online.target

[Service]
User=$BOTUSER
WorkingDirectory=$DIR/trader
ExecStart=$DIR/trader/.venv/bin/python paper_bot.py
Restart=always
RestartSec=60
# keep it from ever competing with other software on this server
CPUQuota=50%
MemoryMax=1500M
MemoryHigh=1200M
Nice=15
IOSchedulingClass=idle
Environment=OMP_NUM_THREADS=1
# sandbox
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$DIR/trader/data
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT

cat > /etc/systemd/system/kenui-listing.service <<UNIT
[Unit]
Description=Kenui listing-short paper bot (fake money, public data only, simulated prop challenge)
After=network-online.target
Wants=network-online.target

[Service]
User=$BOTUSER
WorkingDirectory=$DIR/trader
ExecStart=$DIR/trader/.venv/bin/python -m prop.live.listing_paper
Restart=always
RestartSec=60
CPUQuota=25%
MemoryMax=400M
Nice=15
IOSchedulingClass=idle
Environment=OMP_NUM_THREADS=1
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=$DIR/trader/data
ProtectHome=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable kenui-paper.service kenui-listing.service
systemctl restart kenui-paper.service kenui-listing.service
echo "== started. First cycle takes 3-6 minutes (downloads 41 days of history). Showing the log: =="
sleep 330
journalctl -u kenui-paper.service --no-pager -n 400 --since "-6min" | grep -E "failed|cycle|PAPER|stale|Traceback|Error" | tail -n 15 || true
echo "== Listing bot (second service): =="
journalctl -u kenui-listing.service --no-pager -n 20 | tail -n 6 || true
echo "== Listing report:  sudo -u $BOTUSER bash -c 'cd $DIR/trader && .venv/bin/python -m prop.live.listing_paper --report' =="
echo "== Report any time with:  sudo -u $BOTUSER $DIR/trader/.venv/bin/python $DIR/trader/paper_bot.py --report =="

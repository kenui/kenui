#!/usr/bin/env bash
# Removes the paper bot completely. Nothing else on the server is touched.
set -euo pipefail
systemctl disable --now kenui-paper.service 2>/dev/null || true
rm -f /etc/systemd/system/kenui-paper.service
systemctl daemon-reload
rm -rf /opt/kenui-trader
userdel kenuibot 2>/dev/null || true
echo "paper bot removed"

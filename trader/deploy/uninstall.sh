#!/usr/bin/env bash
# Removes both paper bots completely. Nothing else on the server is touched.
set -euo pipefail
systemctl disable --now kenui-paper.service kenui-listing.service 2>/dev/null || true
rm -f /etc/systemd/system/kenui-paper.service /etc/systemd/system/kenui-listing.service
systemctl daemon-reload
rm -rf /opt/kenui-trader
userdel kenuibot 2>/dev/null || true
echo "paper bots removed"

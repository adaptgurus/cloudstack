#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $EUID -eq 0 ]] || { echo "seal-image.sh requires root" >&2; exit 1; }
systemctl stop layersentryd.service layersentry-maintenance.timer layersentry-privileged.service 2>/dev/null || true
/usr/bin/layersentryd seal
rm -rf /run/layersentryd/*
rm -f /etc/ssh/ssh_host_* /root/.bash_history
find /home -maxdepth 2 -name .bash_history -type f -delete 2>/dev/null || true
if command -v cloud-init >/dev/null 2>&1; then cloud-init clean --logs --seed || true; fi
truncate -s 0 /etc/machine-id
rm -f /var/lib/dbus/machine-id
journalctl --rotate >/dev/null 2>&1 || true
journalctl --vacuum-time=1s >/dev/null 2>&1 || true
dnf clean all >/dev/null
rm -rf /var/cache/dnf/* /tmp/* /var/tmp/*
"$ROOT/image/validate-image.sh" --sealed
printf 'SEAL_OK image=layersentry-single-os-rocky9\n'

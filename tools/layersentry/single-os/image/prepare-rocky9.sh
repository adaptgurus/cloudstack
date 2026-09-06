#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT="$ROOT/agent"
[[ $EUID -eq 0 ]] || { echo "prepare-rocky9.sh requires root" >&2; exit 1; }
source /etc/os-release
[[ "${ID:-}" == rocky && "${VERSION_ID%%.*}" == 9 ]] || { echo "Rocky Linux 9 required" >&2; exit 1; }
management_cidr="${LAYERSENTRY_MANAGEMENT_CIDR:?set LAYERSENTRY_MANAGEMENT_CIDR}"

dnf -y install ca-certificates firewalld audit policycoreutils openssh-server chrony python3 golang systemd-rpm-macros rpm-build podman nginx xfsprogs e2fsprogs util-linux
"$ROOT/rocky9-hardening" apply --management-cidr "$management_cidr"

pushd "$AGENT" >/dev/null
GOTOOLCHAIN=auto go build -trimpath -ldflags='-s -w' -o /usr/bin/layersentryd ./cmd/layersentryd
GOTOOLCHAIN=auto go build -trimpath -ldflags='-s -w' -o /usr/bin/layersentryctl ./cmd/layersentryctl
popd >/dev/null
chmod 0755 /usr/bin/layersentryd /usr/bin/layersentryctl
install -d -o root -g root -m 0700 /var/lib/layersentryd
install -m 0644 "$ROOT/packaging/layersentry-firstboot.service" /usr/lib/systemd/system/layersentry-firstboot.service
install -m 0644 "$ROOT/packaging/layersentryd.service" /usr/lib/systemd/system/layersentryd.service
install -m 0644 "$ROOT/packaging/layersentry-maintenance.service" /usr/lib/systemd/system/layersentry-maintenance.service
install -m 0644 "$ROOT/packaging/layersentry-maintenance.timer" /usr/lib/systemd/system/layersentry-maintenance.timer
systemctl daemon-reload
systemctl enable layersentry-firstboot.service layersentryd.service layersentry-maintenance.timer
"$ROOT/image/validate-image.sh" --pre-seal
printf 'PREPARE_OK rocky=9 management_cidr=%s\n' "$management_cidr"

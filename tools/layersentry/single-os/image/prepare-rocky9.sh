#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ $EUID -eq 0 ]] || { echo "prepare-rocky9.sh requires root" >&2; exit 1; }
source /etc/os-release
[[ "${ID:-}" == rocky && "${VERSION_ID%%.*}" == 9 ]] || { echo "Rocky Linux 9 required" >&2; exit 1; }
management_cidr="${LAYERSENTRY_MANAGEMENT_CIDR:?set LAYERSENTRY_MANAGEMENT_CIDR}"
agent_rpm="${LAYERSENTRY_AGENT_RPM:?set LAYERSENTRY_AGENT_RPM to the prebuilt LayerSentry RPM}"
[[ -f "$agent_rpm" && ! -L "$agent_rpm" ]] || { echo "LayerSentry RPM must be a regular local file" >&2; exit 1; }

dnf -y install ca-certificates firewalld audit policycoreutils openssh-server chrony python3 dnf-plugins-core xfsprogs e2fsprogs util-linux
"$ROOT/rocky9-hardening" apply --management-cidr "$management_cidr"

rpmkeys --checksig "$agent_rpm" | grep -Eiq 'pgp|rsa|signature' || { echo "LayerSentry RPM signature verification failed" >&2; exit 1; }
dnf -y install "$agent_rpm"

# PostgreSQL vendor repository is optional at image-build time but, when supplied,
# must be a local signed repository-definition RPM. No remote script/URL is used.
if [[ -n "${LAYERSENTRY_PGDG_REPO_RPM:-}" ]]; then
  repo_rpm="$LAYERSENTRY_PGDG_REPO_RPM"
  [[ -f "$repo_rpm" && ! -L "$repo_rpm" ]] || { echo "PGDG repo asset must be a regular local file" >&2; exit 1; }
  rpmkeys --checksig "$repo_rpm" | grep -Eiq 'pgp|rsa|signature' || { echo "PGDG repository RPM signature verification failed" >&2; exit 1; }
  dnf -y install "$repo_rpm"
fi

systemd-tmpfiles --create /usr/lib/tmpfiles.d/layersentryd.conf
systemctl daemon-reload
systemctl enable layersentry-firstboot.service layersentryd.service layersentry-maintenance.timer
"$ROOT/image/validate-image.sh" --pre-seal
printf 'PREPARE_OK rocky=9 management_cidr=%s agent_rpm=%s\n' "$management_cidr" "$(basename "$agent_rpm")"

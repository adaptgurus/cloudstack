#!/usr/bin/env bash
set -euo pipefail

[[ ${EUID} -eq 0 ]] || { echo "PREPARE_FAIL reason=root_required" >&2; exit 1; }
source /etc/os-release
[[ "${ID:-}" == "rocky" && "${VERSION_ID%%.*}" == "9" ]] || { echo "PREPARE_FAIL reason=rocky9_required" >&2; exit 1; }

# This is disposable-lab host preparation, not the product provider lifecycle.
# No database/application package is installed here.
dnf -y install \
  ca-certificates firewalld audit policycoreutils policycoreutils-python-utils \
  openssh-server chrony python3 dnf-plugins-core xfsprogs e2fsprogs util-linux \
  iproute lvm2 NetworkManager ansible-core openssl

systemctl enable --now NetworkManager.service firewalld.service chronyd.service

if command -v getenforce >/dev/null; then
  current="$(getenforce)"
  if [[ "$current" == "Permissive" ]]; then
    setenforce 1
  elif [[ "$current" == "Disabled" ]]; then
    echo "PREPARE_FAIL reason=selinux_disabled reboot_with_selinux_enforcing_required" >&2
    exit 1
  fi
fi

grep -Eq '^SELINUX=enforcing$' /etc/selinux/config || \
  sed -ri 's/^SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config

# Optional PGDG repository bootstrap for PostgreSQL 16/17 acceptance. The
# operator/runner supplies a local repository-definition RPM; this script never
# curl-pipes or executes a remote installer. Signature verification is mandatory.
if [[ -n "${LAYERSENTRY_PGDG_REPO_RPM:-}" ]]; then
  repo_rpm="$LAYERSENTRY_PGDG_REPO_RPM"
  [[ -f "$repo_rpm" && ! -L "$repo_rpm" ]] || { echo "PREPARE_FAIL reason=unsafe_pgdg_repo_asset" >&2; exit 1; }
  rpmkeys --checksig "$repo_rpm" | grep -Eiq 'pgp|rsa|signature' || { echo "PREPARE_FAIL reason=pgdg_repo_signature_invalid" >&2; exit 1; }
  dnf -y install "$repo_rpm"
  dnf -q repolist --enabled | awk '{print $1}' | grep -Eq '^pgdg(16|17)$' || { echo "PREPARE_FAIL reason=pgdg16_17_repo_not_enabled" >&2; exit 1; }
fi

# Provider and optional VRRP packages must remain on-demand.
for pkg in postgresql16-server postgresql17-server mysql-server mariadb-server redis valkey nginx httpd tomcat nodejs python3.12 podman keepalived; do
  if rpm -q "$pkg" >/dev/null 2>&1; then
    echo "PREPARE_FAIL reason=provider_package_preinstalled package=$pkg" >&2
    exit 1
  fi
done

systemctl is-active --quiet firewalld.service
systemctl is-enabled --quiet firewalld.service
getenforce | grep -Fxq Enforcing

printf 'PREPARE_OK rocky=%s selinux=%s firewalld=active-enabled root_source=%s pgdg_asset=%s\n' \
  "$VERSION_ID" "$(getenforce)" "$(findmnt -nro SOURCE /)" "${LAYERSENTRY_PGDG_REPO_RPM:+provided}"
printf 'LAB_NOTE root_password_ssh_may_be_enabled_for_disposable_acceptance_only; production_image_policy_remains_key_based_non_root_admin\n'

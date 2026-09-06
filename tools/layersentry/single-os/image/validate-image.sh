#!/usr/bin/env bash
set -euo pipefail
mode="${1:---sealed}"
source /etc/os-release
[[ "${ID:-}" == rocky && "${VERSION_ID%%.*}" == 9 ]] || { echo "FAIL os_not_rocky9"; exit 1; }
command -v layersentryd >/dev/null || { echo "FAIL layersentryd_missing"; exit 1; }
command -v layersentryctl >/dev/null || { echo "FAIL layersentryctl_missing"; exit 1; }
getenforce | grep -Fxq Enforcing || { echo "FAIL selinux_not_enforcing"; exit 1; }
systemctl is-enabled --quiet firewalld || { echo "FAIL firewalld_not_enabled"; exit 1; }
id layersentry >/dev/null 2>&1 || { echo "FAIL layersentry_account_missing"; exit 1; }
systemctl is-enabled --quiet layersentry-privileged.service || { echo "FAIL privileged_helper_not_enabled"; exit 1; }
systemctl is-enabled --quiet layersentry-firstboot.service || { echo "FAIL firstboot_not_enabled"; exit 1; }
systemctl is-enabled --quiet layersentryd.service || { echo "FAIL daemon_not_enabled"; exit 1; }
systemctl is-enabled --quiet layersentry-maintenance.timer || { echo "FAIL maintenance_timer_not_enabled"; exit 1; }
systemctl cat layersentryd.service | grep -Fxq 'User=layersentry' || { echo "FAIL daemon_not_unprivileged"; exit 1; }
systemctl cat layersentry-privileged.service | grep -Fxq 'User=root' || { echo "FAIL helper_not_root_owned"; exit 1; }

if [[ "$mode" == "--sealed" ]]; then
  for path in \
    /var/lib/layersentryd/identity/node-id \
    /var/lib/layersentryd/identity/bootstrap-token \
    /var/lib/layersentryd/identity/tls.key \
    /var/lib/layersentryd/identity/tls.crt \
    /var/lib/layersentryd/identity/secret.key \
    /var/lib/layersentryd/identity/admin.json; do
    [[ ! -e "$path" ]] || { echo "FAIL clone_identity_present=$path"; exit 1; }
  done
  for dir in \
    /var/lib/layersentryd/state/services \
    /var/lib/layersentryd/operations \
    /var/lib/layersentryd/plans \
    /var/lib/layersentryd/checkpoints \
    /var/lib/layersentryd/secrets \
    /var/lib/layersentryd/evidence \
    /var/lib/layersentryd/backups; do
    [[ ! -d "$dir" || -z "$(find "$dir" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]] || { echo "FAIL customer_state_present=$dir"; exit 1; }
  done
  [[ ! -s /etc/machine-id ]] || { echo "FAIL machine_id_not_sealed"; exit 1; }
  for pkg in nginx postgresql16-server postgresql17-server; do
    if rpm -q "$pkg" >/dev/null 2>&1; then
      echo "FAIL provider_package_baked_into_image=$pkg"
      exit 1
    fi
  done
fi
printf 'IMAGE_VALIDATE_OK mode=%s\n' "$mode"

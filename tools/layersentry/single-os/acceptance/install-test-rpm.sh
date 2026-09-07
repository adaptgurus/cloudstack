#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 RPM_PATH EXPECTED_SHA256 [--allow-unsigned-dev]" >&2
}
[[ $# -ge 2 && $# -le 3 ]] || { usage; exit 2; }
rpm_path="$1"
expected_sha="${2,,}"
allow_unsigned="${3:-}"
[[ ${EUID} -eq 0 ]] || { echo "INSTALL_FAIL reason=root_required" >&2; exit 1; }
[[ -f "$rpm_path" && ! -L "$rpm_path" ]] || { echo "INSTALL_FAIL reason=unsafe_rpm_path" >&2; exit 1; }
[[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]] || { echo "INSTALL_FAIL reason=invalid_expected_sha256" >&2; exit 1; }
actual_sha="$(sha256sum "$rpm_path" | awk '{print tolower($1)}')"
[[ "$actual_sha" == "$expected_sha" ]] || { echo "INSTALL_FAIL reason=sha256_mismatch actual=$actual_sha" >&2; exit 1; }

sig_line="$(rpmkeys --checksig "$rpm_path" 2>&1 || true)"
if ! grep -Eiq 'pgp|rsa|signature' <<<"$sig_line"; then
  if [[ "$allow_unsigned" != "--allow-unsigned-dev" ]]; then
    echo "INSTALL_FAIL reason=rpm_signature_missing use_explicit_disposable_dev_exception_if_authorized" >&2
    exit 1
  fi
  echo "LAB_EXCEPTION unsigned_development_rpm=true sha256=$actual_sha"
fi

source /etc/os-release
[[ "${ID:-}" == rocky && "${VERSION_ID%%.*}" == 9 ]] || { echo "INSTALL_FAIL reason=rocky9_required" >&2; exit 1; }
getenforce | grep -Fxq Enforcing || { echo "INSTALL_FAIL reason=selinux_not_enforcing" >&2; exit 1; }
systemctl is-active --quiet firewalld.service || { echo "INSTALL_FAIL reason=firewalld_not_active" >&2; exit 1; }

dnf -y install "$rpm_path"
systemd-sysusers /usr/lib/sysusers.d/layersentryd.conf
systemd-tmpfiles --create /usr/lib/tmpfiles.d/layersentryd.conf
systemctl daemon-reload
systemctl enable --now layersentry-privileged.service
systemctl enable --now layersentry-firstboot.service
systemctl enable --now layersentryd.service
systemctl enable --now layersentry-maintenance.timer

systemctl is-active --quiet layersentry-privileged.service
systemctl is-active --quiet layersentryd.service
id layersentry >/dev/null
[[ -f /usr/lib/layersentry/ansible/ansible.cfg ]]
[[ -f /usr/lib/layersentry/ansible/playbooks/single_os_apply.yml ]]
command -v ansible-playbook >/dev/null

for pkg in postgresql16-server postgresql17-server mysql-server mariadb-server redis valkey nginx httpd tomcat nodejs python3.12 podman keepalived; do
  if rpm -q "$pkg" >/dev/null 2>&1; then
    echo "INSTALL_FAIL reason=provider_package_baked_or_preinstalled package=$pkg" >&2
    exit 1
  fi
done

printf 'INSTALL_OK rpm_sha256=%s daemon=active helper=active ansible_project=present provider_packages=absent\n' "$actual_sha"

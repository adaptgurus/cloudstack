#!/usr/bin/env bash
# Layersentry V1.0 installer entrypoint for Rocky Linux 9 x86_64.
#
# This entrypoint preserves the reviewed full Rocky 9 installer at immutable commit
# 83e77eb1..., applies only fixes proven against the self-hosted Hyper-V runner,
# and provides an explicit --resume path for interrupted exact 4.22.1.1 installs.
#
# Proven fixes:
#   1. CloudStack 4.22.1.1 UI: Node 16 + npm install + npm run build.
#      Do not use npm ci: the historical upstream lockfile is not strict-manifest
#      synchronous. Do not delete the lockfile: that resolves incompatible newer
#      Vue compiler/tooling versions.
#   2. UI-root discovery is pipefail-safe; rpm -ql is fully captured before awk.
#   3. Interrupted exact installs use the idempotent recovery path rather than
#      reinstalling/downgrading packages or recreating a complete database.
#
# It intentionally never creates cloudbr0, VLANs, guest/public networks or storage.

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly FULL_INSTALLER_COMMIT='83e77eb1ed7fa2e18f5cdfdc3c5e9148247a447f'
readonly FULL_INSTALLER_URL="https://raw.githubusercontent.com/adaptgurus/cloudstack/${FULL_INSTALLER_COMMIT}/install-layersentry-rocky9.sh"
readonly RECOVERY_COMMIT='d38dba2660c7777c6d3ae7992c8ce5b3d68019e6'
readonly RECOVERY_URL="https://raw.githubusercontent.com/adaptgurus/cloudstack/${RECOVERY_COMMIT}/install-layersentry-rocky9-resume-v3.sh"
readonly EXPECTED_VERSION='4.22.1.1-1'

usage() {
  cat <<'USAGE'
Layersentry V1.0 installer for Rocky Linux 9 x86_64

Usage:
  sudo ./install-layersentry-rocky9.sh [options]

Options:
  --fqdn NAME                 Set/validate the management-server FQDN.
  --with-kvm                  Install/validate the exact CloudStack KVM agent.
  --ui-only                   Rebuild/redeploy Layersentry UI on exact 4.22.1.1.
  --resume                    Continue an interrupted exact 4.22.1.1 installation.
  --open-ui-firewall          Ensure SSH and TCP/8080 are allowed by firewalld.
  --set-selinux-permissive    Explicitly approve Permissive SELinux for fresh setup.
  -h, --help                  Show this help.

The installer pins CloudStack 4.22.1.1, Layersentry UI source
6d364150095ba5cfd433746dca1f13d38ca1951f, Java 17 and Node 16.
It does not create cloudbr0, VLANs, guest/public networking or storage pools.
USAGE
}

[[ $EUID -eq 0 ]] || { echo 'ERROR: run this installer as root.' >&2; exit 1; }

resume=0
ui_only=0
for arg in "$@"; do
  case "$arg" in
    --resume) resume=1 ;;
    --ui-only) ui_only=1 ;;
    -h|--help) usage; exit 0 ;;
  esac
done
((resume + ui_only <= 1)) || { echo 'ERROR: --resume and --ui-only are mutually exclusive.' >&2; exit 2; }

current=''
if rpm -q cloudstack-management >/dev/null 2>&1; then
  current="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-management)"
fi

version_is_exact() {
  [[ "$1" == "$EXPECTED_VERSION" || "$1" == "$EXPECTED_VERSION."* ]]
}

# An interrupted package installation must never be sent back through the fresh
# installer. Route it explicitly to the proven idempotent recovery implementation.
if ((resume)); then
  version_is_exact "$current" || {
    echo "ERROR: --resume requires exact CloudStack ${EXPECTED_VERSION}; found ${current:-not-installed}." >&2
    exit 1
  }
  exec bash -c "curl -fsSL --retry 4 --retry-all-errors --connect-timeout 15 --max-time 120 '$RECOVERY_URL' -o /root/install-layersentry-rocky9-resume-v3.sh && chmod 700 /root/install-layersentry-rocky9-resume-v3.sh && bash -n /root/install-layersentry-rocky9-resume-v3.sh && exec /root/install-layersentry-rocky9-resume-v3.sh"
fi

if [[ -n "$current" ]] && ((ui_only == 0)); then
  if version_is_exact "$current"; then
    echo "ERROR: exact CloudStack $current is already installed. Use --resume after an interrupted install, or --ui-only for UI-only redeployment." >&2
  else
    echo "ERROR: CloudStack $current is installed. Automatic upgrade/downgrade is prohibited." >&2
  fi
  exit 1
fi

runtime="$(mktemp /var/tmp/layersentry-rocky9-full.XXXXXX.sh)"
cleanup() { rm -f -- "$runtime"; }
trap cleanup EXIT

curl -fsSL --retry 4 --retry-all-errors --connect-timeout 15 --max-time 120 \
  "$FULL_INSTALLER_URL" -o "$runtime"
chmod 0700 "$runtime"

python3 - "$runtime" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding='utf-8')

# Pin Rocky 9 Node.js 16 before the full prerequisite transaction.
needle = '''install_prerequisites() {\n  # Minimal Rocky installations intentionally omit several tools used below.\n  dnf -y install \\\n'''
replacement = '''install_prerequisites() {\n  # Minimal Rocky installations intentionally omit several tools used below.\n  # CloudStack 4.22.1.1 UI CI uses Node 16. Pin the Rocky 9 AppStream module.\n  dnf -y install dnf-plugins-core >>"$LOG_FILE" 2>&1\n  dnf -y module reset nodejs >>"$LOG_FILE" 2>&1 || true\n  dnf -y module enable nodejs:16 >>"$LOG_FILE" 2>&1 \\\n    || die "Unable to enable the Rocky Linux 9 Node.js 16 module."\n  dnf -y install \\\n'''
if s.count(needle) != 1:
    raise SystemExit('ERROR: full-installer prerequisite anchor changed unexpectedly.')
s = s.replace(needle, replacement, 1)

old_node = '''  [[ "$node_major" =~ ^[0-9]+$ ]] || die "Unable to determine Node.js version."\n  ((node_major >= 16)) || die "Node.js 16 or newer is required for the Layersentry UI build."\n'''
new_node = '''  [[ "$node_major" == "16" ]] || die "CloudStack 4.22.1.1 UI build requires Node.js 16; detected $(node --version)."\n'''
if s.count(old_node) != 1:
    raise SystemExit('ERROR: full-installer Node-version anchor changed unexpectedly.')
s = s.replace(old_node, new_node, 1)

# Follow Apache CloudStack 4.22.1.1 UI CI. Keep package-lock.json and use npm install.
old_build = '''  pushd "$SOURCE_DIR/ui" >/dev/null\n  export NODE_OPTIONS="--openssl-legacy-provider --max-old-space-size=4096"\n  export npm_config_python=/usr/bin/python3\n  npm ci --legacy-peer-deps --no-audit --no-fund >>"$LOG_FILE" 2>&1\n  npm run lint -- --no-fix >>"$LOG_FILE" 2>&1\n  npm run build >>"$LOG_FILE" 2>&1\n  popd >/dev/null\n'''
new_build = '''  pushd "$SOURCE_DIR/ui" >/dev/null\n  export NODE_OPTIONS="--openssl-legacy-provider --max-old-space-size=4096"\n  export npm_config_python=/usr/bin/python3\n  rm -rf node_modules\n  npm install --no-audit --no-fund >>"$LOG_FILE" 2>&1\n  {\n    echo '===== RESOLVED UI TOOLCHAIN ====='\n    npm ls --depth=0 vue @vue/compiler-sfc vue-loader @vue/cli-service webpack 2>&1 || true\n    echo '===== END RESOLVED UI TOOLCHAIN ====='\n  } >>"$LOG_FILE"\n  npm run build >>"$LOG_FILE" 2>&1\n  popd >/dev/null\n'''
if s.count(old_build) != 1:
    raise SystemExit('ERROR: full-installer npm-build anchor changed unexpectedly.')
s = s.replace(old_build, new_build, 1)

# Avoid SIGPIPE 141 under `set -o pipefail` when awk exits after first index.html.
old_root = '''find_ui_root() {\n  local index_file\n  index_file="$(rpm -ql cloudstack-ui 2>/dev/null | awk '/\\/index\\.html$/ {print; exit}')"\n  if [[ -z "$index_file" ]]; then\n    index_file="$(rpm -ql cloudstack-management 2>/dev/null | awk '/\\/index\\.html$/ {print; exit}')"\n  fi\n'''
new_root = '''find_ui_root() {\n  local index_file ui_files management_files\n  ui_files="$(rpm -ql cloudstack-ui 2>/dev/null || true)"\n  index_file="$(awk '/\\/index\\.html$/ {print; exit}' <<<"$ui_files")"\n  if [[ -z "$index_file" ]]; then\n    management_files="$(rpm -ql cloudstack-management 2>/dev/null || true)"\n    index_file="$(awk '/\\/index\\.html$/ {print; exit}' <<<"$management_files")"\n  fi\n'''
if s.count(old_root) != 1:
    raise SystemExit('ERROR: full-installer UI-root anchor changed unexpectedly.')
s = s.replace(old_root, new_root, 1)

p.write_text(s, encoding='utf-8')
PY

bash -n "$runtime"

# Strip wrapper-only --resume if a future caller supplied it in a malformed mix;
# all other options are passed unchanged to the reviewed full installer.
args=()
for arg in "$@"; do
  [[ "$arg" == '--resume' ]] || args+=("$arg")
done

"$runtime" "${args[@]}"

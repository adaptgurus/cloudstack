#!/usr/bin/env bash
# Layersentry V1.0 installer for Rocky Linux 10 (x86_64).
# Installs the currently available CloudStack 4.22.1.0 EL10 packages, builds the
# reviewed Layersentry UI (including DBaaS/APaaS), and deploys it to the server.

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly PRODUCT_NAME="Layersentry"
readonly PRODUCT_VERSION="V1.0"
readonly CLOUDSTACK_VERSION="4.22.1.0"
readonly CLOUDSTACK_RELEASE="1"
readonly CLOUDSTACK_CHANNEL="4.22"
readonly CLOUDSTACK_REPO_URL="https://download.cloudstack.org/el/10/4.22/"
readonly LAYERSENTRY_UI_COMMIT="6d364150095ba5cfd433746dca1f13d38ca1951f"
readonly LAYERSENTRY_UI_ARCHIVE="https://github.com/adaptgurus/cloudstack/archive/${LAYERSENTRY_UI_COMMIT}.tar.gz"
readonly MIN_RAM_MB=8192
readonly MIN_FREE_DISK_GB=80

BRANDING_ONLY=0
WITH_KVM=0
ALLOW_SELINUX_PERMISSIVE=0
REQUESTED_FQDN=""
PRIMARY_IP=""
LOG_FILE=""
WORK_DIR=""
UI_ROOT=""
SECRETS_FILE="/root/layersentry-v1.0-secrets.txt"
CURRENT_STAGE="initialization"
CURRENT_PROGRESS=0

usage() {
  cat <<USAGE
${PRODUCT_NAME} ${PRODUCT_VERSION} installer for Rocky Linux 10

Usage:
  sudo ./install-layersentry-rocky10.sh [options]

Options:
  --fqdn NAME                  Set/validate the management-server FQDN.
                               Example: layersentry.lab.local
  --set-selinux-permissive     Explicitly allow changing SELinux from Enforcing
                               to Permissive, as required by this CloudStack setup.
  --with-kvm                   Also install the CloudStack KVM agent after checking
                               CPU virtualization and /dev/kvm. Bridge/VLAN/storage
                               networking is never created automatically.
  --branding-only              Rebuild and deploy only the Layersentry UI on an
                               existing CloudStack ${CLOUDSTACK_VERSION} installation.
  -h, --help                   Show this help.

Optional environment variables:
  LAYERSENTRY_CLOUD_DB_PASSWORD
      CloudStack database-user password. When omitted, a random password is generated
      and stored in ${SECRETS_FILE} with mode 0600.

  LAYERSENTRY_DB_DEPLOY_PASSWORD
      MySQL administrative password, only when local root socket authentication is
      unavailable. It is never printed or written to the installation log.

Fresh-install target:
  Rocky Linux 10 x86_64 + CloudStack ${CLOUDSTACK_VERSION} community EL10 packages.
USAGE
}

log_raw() {
  local message="$*"
  printf '%s\n' "$message"
  if [[ -n "${LOG_FILE:-}" ]]; then
    printf '%s\n' "$message" >> "$LOG_FILE"
  fi
}

info() { log_raw "INFO: $*"; }
warn() { log_raw "WARN: $*"; }
die() { log_raw "ERROR: $*" >&2; exit 1; }

progress() {
  CURRENT_PROGRESS="$1"
  CURRENT_STAGE="$2"
  log_raw "[${CURRENT_PROGRESS}%] ${CURRENT_STAGE}"
}

on_error() {
  local rc=$?
  local line=${BASH_LINENO[0]:-unknown}
  set +e
  printf 'ERROR: %s %s failed at [%s%%] %s (line %s, exit %s).\n' \
    "$PRODUCT_NAME" "$PRODUCT_VERSION" "$CURRENT_PROGRESS" "$CURRENT_STAGE" "$line" "$rc" >&2
  if [[ -n "${LOG_FILE:-}" ]]; then
    printf 'Review log: %s\n' "$LOG_FILE" >&2
  fi
  exit "$rc"
}

cleanup() {
  if [[ -n "${WORK_DIR:-}" && -d "$WORK_DIR" ]]; then
    rm -rf "$WORK_DIR"
  fi
}

trap on_error ERR
trap cleanup EXIT

parse_args() {
  while (($#)); do
    case "$1" in
      --fqdn)
        [[ $# -ge 2 ]] || die "--fqdn requires a value"
        REQUESTED_FQDN="$2"
        shift
        ;;
      --set-selinux-permissive) ALLOW_SELINUX_PERMISSIVE=1 ;;
      --with-kvm) WITH_KVM=1 ;;
      --branding-only) BRANDING_ONLY=1 ;;
      -h|--help) usage; exit 0 ;;
      *) die "Unknown argument: $1" ;;
    esac
    shift
  done
}

require_root() {
  [[ ${EUID} -eq 0 ]] || die "Run as root, for example: sudo $0 --fqdn layersentry.lab.local --set-selinux-permissive"
}

init_runtime() {
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  LOG_FILE="/var/log/layersentry-rocky10-${stamp}.log"
  touch "$LOG_FILE"
  chmod 0600 "$LOG_FILE"
  WORK_DIR="$(mktemp -d /var/tmp/layersentry-install.XXXXXX)"
}

validate_os() {
  [[ -r /etc/os-release ]] || die "/etc/os-release is missing"
  # shellcheck disable=SC1091
  . /etc/os-release
  [[ "${ID:-}" == "rocky" ]] || die "This installer is only for Rocky Linux 10; detected '${ID:-unknown}'."
  [[ "${VERSION_ID%%.*}" == "10" ]] || die "This installer requires Rocky Linux 10; detected '${VERSION_ID:-unknown}'."
  [[ "$(uname -m)" == "x86_64" ]] || die "Only x86_64 is supported by this installer."
}

find_primary_ip() {
  PRIMARY_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}')"
  if [[ -z "$PRIMARY_IP" ]]; then
    PRIMARY_IP="$(hostname -I 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i ~ /^[0-9]+\./) {print $i; exit}}')"
  fi
  [[ -n "$PRIMARY_IP" ]] || die "Unable to detect a primary IPv4 address. Configure a static management IP first."
}

configure_fqdn() {
  if [[ -n "$REQUESTED_FQDN" ]]; then
    [[ "$REQUESTED_FQDN" == *.* ]] || die "--fqdn must contain a domain suffix, for example layersentry.lab.local"
    [[ "$REQUESTED_FQDN" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*[A-Za-z0-9]$ ]] || die "Invalid FQDN: $REQUESTED_FQDN"
    hostnamectl set-hostname "$REQUESTED_FQDN"

    local short_name
    short_name="${REQUESTED_FQDN%%.*}"
    if ! grep -Eq "^[[:space:]]*${PRIMARY_IP//./\\.}[[:space:]].*${REQUESTED_FQDN//./\\.}([[:space:]]|$)" /etc/hosts; then
      cp -a /etc/hosts "/etc/hosts.layersentry-backup.$(date +%Y%m%d-%H%M%S)"
      printf '%s %s %s\n' "$PRIMARY_IP" "$REQUESTED_FQDN" "$short_name" >> /etc/hosts
    fi
  fi

  local detected_fqdn
  detected_fqdn="$(hostname -f 2>/dev/null || true)"
  [[ "$detected_fqdn" == *.* ]] || die "A valid FQDN is required. Rerun with --fqdn layersentry.lab.local"
  info "Management FQDN: $detected_fqdn"
}

check_resources() {
  local ram_mb disk_kb disk_gb
  ram_mb="$(awk '/MemTotal:/ {print int($2/1024)}' /proc/meminfo)"
  disk_kb="$(df -Pk / | awk 'NR==2 {print $4}')"
  disk_gb=$((disk_kb / 1024 / 1024))
  ((ram_mb >= MIN_RAM_MB)) || die "At least ${MIN_RAM_MB} MiB RAM is required; detected ${ram_mb} MiB."
  if ((BRANDING_ONLY == 0)); then
    ((disk_gb >= MIN_FREE_DISK_GB)) || die "At least ${MIN_FREE_DISK_GB} GiB free on / is required; detected ${disk_gb} GiB."
  fi
  ip route show default | grep -q '^default' || die "No default route is configured."
  getent hosts download.cloudstack.org >/dev/null 2>&1 || die "DNS cannot resolve download.cloudstack.org."
  getent hosts github.com >/dev/null 2>&1 || die "DNS cannot resolve github.com; the Layersentry UI source cannot be downloaded."
  info "Pre-flight: ${ram_mb} MiB RAM, ${disk_gb} GiB free root disk, IP ${PRIMARY_IP}."
}

configure_selinux() {
  command -v getenforce >/dev/null 2>&1 || return 0
  local mode
  mode="$(getenforce)"
  if [[ "$mode" == "Enforcing" ]]; then
    ((ALLOW_SELINUX_PERMISSIVE)) || die "SELinux is Enforcing. Rerun with --set-selinux-permissive after approval."
    cp -a /etc/selinux/config "/etc/selinux/config.layersentry-backup.$(date +%Y%m%d-%H%M%S)"
    setenforce 0
    sed -ri 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config
    warn "SELinux changed to Permissive by explicit command-line approval."
  else
    info "SELinux mode: $mode"
  fi
}

install_prerequisites() {
  dnf -y install dnf-plugins-core ca-certificates curl tar gzip jq python3 git gcc-c++ make openssl rsync chrony >>"$LOG_FILE" 2>&1
  if ! dnf config-manager --set-enabled crb >>"$LOG_FILE" 2>&1; then
    dnf config-manager setopt crb.enabled=1 >>"$LOG_FILE" 2>&1 \
      || warn "Rocky CRB repository could not be enabled automatically."
  fi
  dnf -y install epel-release >>"$LOG_FILE" 2>&1
  dnf -y install genisoimage >>"$LOG_FILE" 2>&1

  dnf -y install nodejs >>"$LOG_FILE" 2>&1
  command -v npm >/dev/null 2>&1 || dnf -y install npm >>"$LOG_FILE" 2>&1
  command -v node >/dev/null 2>&1 || die "Node.js installation failed."
  command -v npm >/dev/null 2>&1 || die "npm installation failed."

  systemctl enable --now chronyd >>"$LOG_FILE" 2>&1
}

configure_cloudstack_repo() {
  cat > /etc/yum.repos.d/cloudstack.repo <<REPO
[cloudstack]
name=Apache CloudStack ${CLOUDSTACK_CHANNEL} community packages for EL10
baseurl=${CLOUDSTACK_REPO_URL}
enabled=1
gpgcheck=0
repo_gpgcheck=0
REPO
  dnf clean metadata >>"$LOG_FILE" 2>&1
  dnf -q makecache --disablerepo='*' --enablerepo=cloudstack >>"$LOG_FILE" 2>&1
}

package_available() {
  local package="$1"
  dnf -q --disablerepo='*' --enablerepo=cloudstack list --showduplicates "$package" 2>/dev/null \
    | grep -F "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" >/dev/null
}

verify_cloudstack_packages() {
  package_available cloudstack-management || die "cloudstack-management ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE} is unavailable in ${CLOUDSTACK_REPO_URL}"
  package_available cloudstack-ui || die "cloudstack-ui ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE} is unavailable in ${CLOUDSTACK_REPO_URL}"
  if ((WITH_KVM)); then
    package_available cloudstack-agent || die "cloudstack-agent ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE} is unavailable in ${CLOUDSTACK_REPO_URL}"
  fi
}

installed_cloudstack_version() {
  rpm -q --qf '%{VERSION}-%{RELEASE}' cloudstack-management 2>/dev/null || true
}

install_cloudstack() {
  local installed
  installed="$(installed_cloudstack_version)"
  if [[ -n "$installed" ]]; then
    [[ "$installed" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" ]] \
      || die "Installed cloudstack-management is $installed; expected ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}. Automatic upgrade/downgrade is refused."
    info "CloudStack $installed is already installed."
    return 0
  fi

  ((BRANDING_ONLY == 0)) || die "--branding-only requires an existing CloudStack ${CLOUDSTACK_VERSION} installation."

  dnf -y install java-17-openjdk-headless mysql8.4-server >>"$LOG_FILE" 2>&1
  dnf -y --enablerepo=cloudstack install \
    "cloudstack-management-${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" \
    "cloudstack-ui-${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" >>"$LOG_FILE" 2>&1

  installed="$(installed_cloudstack_version)"
  [[ "$installed" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" ]] \
    || die "Installed CloudStack version '$installed' does not match the required version."

  java -version 2>&1 | head -1 | grep -F '17' >/dev/null \
    || die "Java 17 is not the active runtime. Run: alternatives --config java"
}

configure_mysql() {
  ((BRANDING_ONLY == 0)) || return 0

  install -d -m 0755 /etc/my.cnf.d
  local cnf="/etc/my.cnf.d/cloudstack.cnf"
  [[ ! -e "$cnf" ]] || cp -a "$cnf" "${cnf}.layersentry-backup.$(date +%Y%m%d-%H%M%S)"
  cat > "$cnf" <<'MYSQLCONF'
[mysqld]
server_id=1
innodb_rollback_on_timeout=1
innodb_lock_wait_timeout=600
max_connections=350
log_bin=mysql-bin
binlog_format=ROW
MYSQLCONF

  systemctl enable --now mysqld >>"$LOG_FILE" 2>&1
  systemctl restart mysqld >>"$LOG_FILE" 2>&1
  systemctl is-active --quiet mysqld || die "mysqld is not active."
}

generate_database_password() {
  if [[ -z "${LAYERSENTRY_CLOUD_DB_PASSWORD:-}" ]]; then
    LAYERSENTRY_CLOUD_DB_PASSWORD="$(openssl rand -hex 16)"
  fi
  [[ ${#LAYERSENTRY_CLOUD_DB_PASSWORD} -ge 16 ]] || die "LAYERSENTRY_CLOUD_DB_PASSWORD must contain at least 16 characters."

  cat > "$SECRETS_FILE" <<SECRETS
${PRODUCT_NAME} ${PRODUCT_VERSION} installation secrets
Generated: $(date --iso-8601=seconds)

CloudStack database user: cloud
CloudStack database password: ${LAYERSENTRY_CLOUD_DB_PASSWORD}

Initial UI username: admin
Initial UI password: password
IMPORTANT: Change the UI password immediately after first login.
SECRETS
  chmod 0600 "$SECRETS_FILE"
}

configure_cloudstack_database() {
  ((BRANDING_ONLY == 0)) || return 0

  if mysql -NBe "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='cloud'" 2>/dev/null | grep -qx cloud; then
    die "Database 'cloud' already exists. Refusing to recreate it. Use --branding-only for an existing deployment."
  fi

  generate_database_password

  local deploy_arg="--deploy-as=root"
  if [[ -n "${LAYERSENTRY_DB_DEPLOY_PASSWORD:-}" ]]; then
    deploy_arg="--deploy-as=root:${LAYERSENTRY_DB_DEPLOY_PASSWORD}"
  fi

  # This command contains a secret by design. Never echo it and never enable shell tracing.
  cloudstack-setup-databases \
    "cloud:${LAYERSENTRY_CLOUD_DB_PASSWORD}@localhost" \
    "$deploy_arg" \
    -i "$PRIMARY_IP" >>"$LOG_FILE" 2>&1

  unset LAYERSENTRY_CLOUD_DB_PASSWORD LAYERSENTRY_DB_DEPLOY_PASSWORD || true
}

configure_management_server() {
  ((BRANDING_ONLY == 0)) || return 0
  cloudstack-setup-management >>"$LOG_FILE" 2>&1
}

install_kvm_agent() {
  ((WITH_KVM)) || return 0

  grep -Eq '(vmx|svm)' /proc/cpuinfo || die "CPU virtualization extensions are not exposed."
  [[ -e /dev/kvm ]] || die "/dev/kvm is unavailable. Enable hardware or nested virtualization first."

  dnf -y --enablerepo=cloudstack install \
    "cloudstack-agent-${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" >>"$LOG_FILE" 2>&1

  warn "KVM agent installed. Bridge, VLAN, storage and libvirt network configuration were intentionally not guessed."
}

patch_layersentry_source() {
  local source_root="$1"
  python3 - "$source_root/ui/public/config.json" "$source_root/ui/package.json" <<'PY'
import json
import sys

config_path, package_path = sys.argv[1:3]
with open(config_path, encoding='utf-8') as f:
    cfg = json.load(f)

cfg.update({
    'appTitle': 'Layersentry',
    'loginTitle': 'Layersentry',
    'loginFooter': 'Secure private cloud management.',
    'footer': 'Layersentry V1.0',
    'docBase': '',
    'notifyLatestCSVersion': False,
    'apidocs': False,
})
cfg['logo'] = 'assets/layersentry-logo.svg'
cfg['minilogo'] = 'assets/layersentry-icon.svg'
cfg['banner'] = 'assets/layersentry-logo.svg'
cfg['favicon'] = 'assets/layersentry-icon.svg'
cfg['loginFavicon'] = 'assets/layersentry-icon.svg'

user_card = cfg.setdefault('userCard', {})
user_card['enabled'] = False
user_card['links'] = []

theme = cfg.setdefault('theme', {})
theme.update({
    '@layout-mode': 'light',
    '@navigation-background-color': '#10272c',
    '@project-nav-background-color': '#10272c',
    '@project-nav-text-color': 'rgba(255, 255, 255, 0.86)',
    '@navigation-text-color': 'rgba(255, 255, 255, 0.86)',
    '@primary-color': '#0f8f8d',
    '@link-color': '#0f8f8d',
    '@link-hover-color': '#0b6f70',
    '@loading-color': '#0f8f8d',
    '@processing-color': '#0f8f8d',
    '@success-color': '#1f8f55',
    '@warning-color': '#c77800',
    '@error-color': '#c33c3c',
})

with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
    f.write('\n')

with open(package_path, encoding='utf-8') as f:
    pkg = json.load(f)
pkg['name'] = 'layersentry-ui'
pkg['description'] = 'Layersentry private cloud management UI'
pkg['version'] = '1.0.0'
with open(package_path, 'w', encoding='utf-8') as f:
    json.dump(pkg, f, indent=2, ensure_ascii=False)
    f.write('\n')
PY

  python3 - "$source_root/ui/src/style/layersentry.less" "$source_root/ui/src/views/layersentry/ServiceCatalog.vue" <<'PY'
import pathlib
import sys

style = pathlib.Path(sys.argv[1])
text = style.read_text(encoding='utf-8')
replacements = {
    '--ls-brand: #000f42;': '--ls-brand: #0f8f8d;',
    '--ls-nav: #071536;': '--ls-nav: #10272c;',
    '--ls-primary: #1849b5;': '--ls-primary: #0f8f8d;',
    '--ls-primary-hover: #123a91;': '--ls-primary-hover: #0b6f70;',
    '--ls-focus: #84adff;': '--ls-focus: #75d8d5;',
}
for old, new in replacements.items():
    text = text.replace(old, new)
style.write_text(text, encoding='utf-8')

catalog = pathlib.Path(sys.argv[2])
text = catalog.read_text(encoding='utf-8')
text = text.replace('#1849b5', '#0f8f8d')
text = text.replace('rgba(24, 73, 181, 0.08)', 'rgba(15, 143, 141, 0.10)')
catalog.write_text(text, encoding='utf-8')
PY
}

locate_ui_root() {
  local index_path
  index_path="$(rpm -ql cloudstack-ui 2>/dev/null | awk '/\/index\.html$/ {print; exit}')"
  if [[ -z "$index_path" ]]; then
    index_path="$(rpm -ql cloudstack-management 2>/dev/null | awk '/\/index\.html$/ {print; exit}')"
  fi
  if [[ -n "$index_path" ]]; then
    UI_ROOT="$(dirname "$index_path")"
  elif [[ -d /usr/share/cloudstack-management/webapp ]]; then
    UI_ROOT="/usr/share/cloudstack-management/webapp"
  else
    die "Unable to locate the installed CloudStack UI web root."
  fi
  [[ -d "$UI_ROOT" ]] || die "Detected UI root does not exist: $UI_ROOT"
  info "Installed UI root: $UI_ROOT"
}

build_and_deploy_layersentry_ui() {
  local archive="$WORK_DIR/layersentry-ui.tar.gz"
  info "Downloading immutable Layersentry UI source commit ${LAYERSENTRY_UI_COMMIT}."
  curl -fL --retry 5 --retry-all-errors --connect-timeout 15 \
    "$LAYERSENTRY_UI_ARCHIVE" -o "$archive" >>"$LOG_FILE" 2>&1

  tar -xzf "$archive" -C "$WORK_DIR"
  local source_root
  source_root="$(find "$WORK_DIR" -mindepth 1 -maxdepth 1 -type d -name 'cloudstack-*' | head -1)"
  [[ -n "$source_root" && -d "$source_root/ui" ]] || die "Downloaded archive does not contain the expected CloudStack UI source."

  patch_layersentry_source "$source_root"

  pushd "$source_root/ui" >/dev/null
  export NODE_OPTIONS="--max-old-space-size=4096"
  npm install --legacy-peer-deps --no-audit --no-fund >>"$LOG_FILE" 2>&1
  if ! npm run build >>"$LOG_FILE" 2>&1; then
    warn "Initial UI build failed; retrying with the OpenSSL legacy provider required by some Webpack 4 environments."
    export NODE_OPTIONS="--openssl-legacy-provider --max-old-space-size=4096"
    npm run build >>"$LOG_FILE" 2>&1
  fi
  [[ -f dist/index.html ]] || die "Layersentry UI build completed without dist/index.html."
  popd >/dev/null

  locate_ui_root
  install -d -m 0700 /var/backups/layersentry
  local backup="/var/backups/layersentry/ui-$(date +%Y%m%d-%H%M%S).tar.gz"
  tar -C "$UI_ROOT" -czf "$backup" .
  chmod 0600 "$backup"

  rsync -a "$source_root/ui/dist/" "$UI_ROOT/"
  [[ -f "$UI_ROOT/index.html" ]] || die "UI deployment did not create $UI_ROOT/index.html."
  info "Previous UI backed up to $backup"
}

configure_firewall() {
  if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-port=8080/tcp >>"$LOG_FILE" 2>&1
    firewall-cmd --reload >>"$LOG_FILE" 2>&1
    info "Opened TCP 8080 for the web UI. Ports 8096 and 8250 were not exposed."
  else
    warn "firewalld is not active. Review host and upstream firewall rules manually."
  fi
}

restart_and_verify() {
  systemctl restart cloudstack-management >>"$LOG_FILE" 2>&1
  systemctl is-active --quiet cloudstack-management || die "cloudstack-management is not active after restart."

  local url="http://127.0.0.1:8080/client/" code="" attempt
  for attempt in $(seq 1 120); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 3 --max-time 5 "$url" || true)"
    case "$code" in
      200|302|401) info "Web endpoint responded with HTTP $code."; return 0 ;;
    esac
    sleep 5
  done
  die "Management service is active but $url did not become ready. Last HTTP code: ${code:-none}."
}

main() {
  parse_args "$@"
  require_root
  init_runtime

  log_raw "${PRODUCT_NAME} ${PRODUCT_VERSION} Rocky Linux 10 installer"
  log_raw "Log: $LOG_FILE"

  progress 5 "Validating Rocky Linux 10 host"
  validate_os
  find_primary_ip
  configure_fqdn
  check_resources
  configure_selinux

  progress 15 "Installing Rocky Linux 10 prerequisites"
  install_prerequisites

  progress 28 "Configuring and validating CloudStack EL10 repository"
  configure_cloudstack_repo
  verify_cloudstack_packages

  progress 40 "Installing CloudStack ${CLOUDSTACK_VERSION}"
  install_cloudstack

  progress 52 "Configuring MySQL 8.4"
  configure_mysql

  progress 62 "Initializing CloudStack database"
  configure_cloudstack_database

  progress 70 "Configuring management server"
  configure_management_server
  install_kvm_agent

  progress 80 "Building Layersentry V1.0 UI with DBaaS and APaaS"
  build_and_deploy_layersentry_ui

  progress 92 "Applying firewall policy and restarting services"
  configure_firewall
  restart_and_verify

  progress 100 "Layersentry V1.0 installation completed"
  log_raw "Access URL: http://${PRIMARY_IP}:8080/client/"
  if [[ -f "$SECRETS_FILE" ]]; then
    log_raw "Root-only credentials file: $SECRETS_FILE"
  fi
  log_raw "Initial UI login: admin / password — change it immediately."
  log_raw "Internal CloudStack package/service/API names are intentionally preserved."
  log_raw "Do not expose management ports 8096 or 8250 to the public Internet."
}

main "$@"

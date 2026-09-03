#!/usr/bin/env bash
# Layersentry installer / branding overlay for Apache CloudStack 4.22.1.1 LTS.
# Keeps Apache CloudStack package, service, API, database and internal identifiers unchanged.

set -Eeuo pipefail
IFS=$'\n\t'
umask 022

readonly PRODUCT_NAME="Layersentry"
readonly CLOUDSTACK_VERSION="4.22.1.1"
readonly CLOUDSTACK_CHANNEL="4.22"
readonly ASSET_COMMIT="7a9fdcafd77192a15129c02fcf9aef9076b7d31a"
readonly ASSET_BASE_URL="https://raw.githubusercontent.com/adaptgurus/cloudstack/${ASSET_COMMIT}/ui/public"
readonly SOURCE_BASE_URL="https://raw.githubusercontent.com/adaptgurus/cloudstack/${ASSET_COMMIT}/ui"
readonly LOGO_SHA256="8d5100f54a5590c7d27245ea491c2592da8c6982b1a582cafd785840891da3f1"
readonly ICON_SHA256="235782b2a7dab1d91ed5d3c99411abd75042bcf2f5f3b784a753123bf5e579da"
readonly STYLE_SHA256="5a531679566bd3a8b88f061f682ce940fb8adeb7cbc1f71b9700441866a5cdca"
readonly MIN_RAM_MB=4096
readonly MIN_DISK_GB=250

BRANDING_ONLY=0
WITH_KVM=0
SET_SELINUX_PERMISSIVE=0
DB_HOST="localhost"
DB_DEPLOY_USER="root"
CURRENT_PROGRESS=0
CURRENT_STAGE="initialization"
INSTALL_MODE="fresh"
PKG_FAMILY=""
OS_ID=""
OS_VERSION=""
OS_CODENAME=""
OS_MAJOR=""
PRIMARY_IP=""
UI_ROOT=""
CONFIG_FILE=""
ASSETS_DIR=""
LOG_FILE=""
TMP_DIR=""

usage() {
  cat <<USAGE
Usage: sudo ./install-layersentry.sh [options]

Installs Apache CloudStack ${CLOUDSTACK_VERSION} LTS where supported, then applies
Layersentry presentation branding without renaming CloudStack internals.

Options:
  --branding-only              Apply/refresh Layersentry branding on an existing
                               CloudStack ${CLOUDSTACK_VERSION} installation.
  --with-kvm                   Also install the matching CloudStack KVM agent after
                               verifying hardware/nested virtualization. This script
                               does not guess or rewrite host bridge networking.
  --db-host HOST               Database host for a fresh install (default: localhost).
  --db-deploy-user USER        Database administrative user (default: root).
  --set-selinux-permissive     On EL hosts only, explicitly allow this script to set
                               SELinux permissive as documented for basic CloudStack
                               setup. Without this flag, enforcing SELinux is a stop.
  -h, --help                   Show this help.

Fresh-install database secrets are never logged. Supply optional environment variables:
  LAYERSENTRY_CLOUD_DB_PASSWORD   Password for the CloudStack database user.
  LAYERSENTRY_DB_DEPLOY_PASSWORD  Administrative DB password when socket/no-password
                                  authentication is not available.

Supported deterministic automation targets:
  - Ubuntu 22.04 (jammy), 24.04 (noble)
  - Debian 12 (bookworm)
  - EL-compatible 8/9/10 x86_64 when the exact ${CLOUDSTACK_VERSION} community package
    is present in the current CloudStack EL repository
  - SLES/openSUSE 15.6+ x86_64 when the exact package is present in the current repo

The script rejects missing exact-version packages rather than installing a different,
snapshot, RC, beta or arbitrary version.
USAGE
}

log_raw() {
  local msg="$*"
  if [[ -n "${LOG_FILE:-}" ]]; then
    printf '%s\n' "$msg" | tee -a "$LOG_FILE"
  else
    printf '%s\n' "$msg"
  fi
}

info() { log_raw "INFO: $*"; }
warn() { log_raw "WARN: $*"; }
die() { log_raw "ERROR: $*"; exit 1; }

progress() {
  CURRENT_PROGRESS="$1"
  CURRENT_STAGE="$2"
  log_raw "[${CURRENT_PROGRESS}%] ${CURRENT_STAGE}"
}

on_error() {
  local rc=$?
  local line=${BASH_LINENO[0]:-unknown}
  set +e
  printf 'ERROR: Layersentry installer failed at [%s%%] %s (line %s, exit %s).\n' \
    "$CURRENT_PROGRESS" "$CURRENT_STAGE" "$line" "$rc" | tee -a "$LOG_FILE" >&2
  printf 'ERROR: Review %s. No 100%% completion marker was emitted.\n' "$LOG_FILE" | tee -a "$LOG_FILE" >&2
  exit "$rc"
}

cleanup() {
  if [[ -n "${TMP_DIR:-}" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
}

trap on_error ERR
trap cleanup EXIT

parse_args() {
  while (($#)); do
    case "$1" in
      --branding-only) BRANDING_ONLY=1 ;;
      --with-kvm) WITH_KVM=1 ;;
      --db-host)
        [[ $# -ge 2 ]] || die "--db-host requires a value"
        DB_HOST="$2"; shift ;;
      --db-deploy-user)
        [[ $# -ge 2 ]] || die "--db-deploy-user requires a value"
        DB_DEPLOY_USER="$2"; shift ;;
      --set-selinux-permissive) SET_SELINUX_PERMISSIVE=1 ;;
      -h|--help) usage; exit 0 ;;
      *) printf 'Unknown argument: %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
  done
}

require_root() {
  [[ ${EUID} -eq 0 ]] || die "Run this installer as root (for example: sudo $0)."
}

init_logging() {
  local stamp
  stamp="$(date +%Y%m%d-%H%M%S)"
  LOG_FILE="/var/log/layersentry-install-${stamp}.log"
  touch "$LOG_FILE"
  chmod 0600 "$LOG_FILE"
  TMP_DIR="$(mktemp -d /tmp/layersentry-install.XXXXXX)"
}

command_exists() { command -v "$1" >/dev/null 2>&1; }

install_bootstrap_tools() {
  case "$PKG_FAMILY" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      apt-get update -y >>"$LOG_FILE" 2>&1
      apt-get install -y ca-certificates curl gnupg python3 >>"$LOG_FILE" 2>&1
      ;;
    dnf)
      dnf install -y ca-certificates curl python3 >>"$LOG_FILE" 2>&1
      ;;
    zypper)
      zypper --non-interactive install ca-certificates curl python3 >>"$LOG_FILE" 2>&1
      ;;
  esac
}

detect_os() {
  [[ -r /etc/os-release ]] || die "Cannot detect Linux distribution: /etc/os-release is missing."
  # shellcheck disable=SC1091
  . /etc/os-release
  OS_ID="${ID:-unknown}"
  OS_VERSION="${VERSION_ID:-unknown}"
  OS_CODENAME="${VERSION_CODENAME:-}"
  OS_MAJOR="${OS_VERSION%%.*}"

  local arch
  arch="$(uname -m)"
  [[ "$arch" == "x86_64" ]] || die "Unsupported architecture '$arch'. This installer targets the selected release's x86_64 management-server packages."

  case "$OS_ID" in
    ubuntu)
      PKG_FAMILY="apt"
      case "$OS_VERSION" in
        22.04) OS_CODENAME="jammy" ;;
        24.04) OS_CODENAME="noble" ;;
        *) die "Ubuntu $OS_VERSION is not an installer-supported target for CloudStack ${CLOUDSTACK_VERSION}. Use Ubuntu 22.04 or 24.04." ;;
      esac
      ;;
    debian)
      PKG_FAMILY="apt"
      [[ "$OS_MAJOR" == "12" ]] || die "Debian $OS_VERSION is not an installer-supported target. Debian 12 (bookworm) is supported here."
      OS_CODENAME="bookworm"
      ;;
    rhel|rocky|almalinux|centos|ol)
      PKG_FAMILY="dnf"
      case "$OS_MAJOR" in 8|9|10) ;; *) die "EL-compatible major $OS_MAJOR is outside this installer's supported range (8/9/10)." ;; esac
      ;;
    sles|opensuse-leap)
      PKG_FAMILY="zypper"
      python3 - "$OS_VERSION" <<'PY' || die "SLES/openSUSE $OS_VERSION is below the supported 15.6 baseline."
import sys
v=tuple(int(x) for x in sys.argv[1].split('.')[:2])
raise SystemExit(0 if v >= (15,6) else 1)
PY
      ;;
    *)
      die "Unsupported distribution: ${OS_ID} ${OS_VERSION}. No unsafe package-repository guess will be made."
      ;;
  esac

  info "Detected ${OS_ID} ${OS_VERSION} (${PKG_FAMILY}), x86_64."
}

check_resources() {
  local ram_mb disk_kb disk_gb
  ram_mb="$(awk '/MemTotal:/ {print int($2/1024)}' /proc/meminfo)"
  disk_kb="$(df -Pk / | awk 'NR==2 {print $4}')"
  disk_gb=$((disk_kb / 1024 / 1024))

  ((ram_mb >= MIN_RAM_MB)) || die "Insufficient RAM: ${ram_mb} MiB detected; CloudStack management requires at least ${MIN_RAM_MB} MiB."
  if [[ "$INSTALL_MODE" == "fresh" ]]; then
    ((disk_gb >= MIN_DISK_GB)) || die "Insufficient free root-filesystem space: ${disk_gb} GiB; this installer requires ${MIN_DISK_GB} GiB for a fresh management node."
  fi

  local fqdn
  fqdn="$(hostname -f 2>/dev/null || true)"
  if [[ "$INSTALL_MODE" == "fresh" && "$fqdn" != *.* ]]; then
    die "A fully qualified domain name is required for a fresh management server; 'hostname -f' returned '${fqdn:-empty}'."
  fi

  PRIMARY_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  [[ -n "$PRIMARY_IP" ]] || die "No primary IPv4 address could be detected. Configure a static management address before installation."
  ip route show default >/dev/null 2>&1 || die "No default route detected."

  if ! getent hosts download.cloudstack.org >/dev/null 2>&1; then
    die "DNS resolution for download.cloudstack.org failed."
  fi

  info "Pre-flight resources: RAM ${ram_mb} MiB, free root disk ${disk_gb} GiB, management IP ${PRIMARY_IP}."
}

installed_cs_version() {
  case "$PKG_FAMILY" in
    apt)
      dpkg-query -W -f='${Version}' cloudstack-management 2>/dev/null || true
      ;;
    dnf|zypper)
      rpm -q --qf '%{VERSION}' cloudstack-management 2>/dev/null || true
      ;;
  esac
}

detect_install_mode() {
  local current
  current="$(installed_cs_version)"
  if [[ -n "$current" ]]; then
    INSTALL_MODE="branding-update"
    if [[ "$current" != "$CLOUDSTACK_VERSION" && "$current" != "$CLOUDSTACK_VERSION"-* && "$current" != *:"$CLOUDSTACK_VERSION"* ]]; then
      die "Existing cloudstack-management version '$current' is not ${CLOUDSTACK_VERSION}. Refusing an automatic production upgrade/downgrade. Upgrade CloudStack separately, then rerun --branding-only."
    fi
    info "Existing CloudStack ${current} detected; database/package reinstall is disabled."
  elif ((BRANDING_ONLY)); then
    die "--branding-only was requested but cloudstack-management is not installed."
  else
    INSTALL_MODE="fresh"
  fi
}

check_selinux() {
  [[ "$PKG_FAMILY" == "dnf" ]] || return 0
  command_exists getenforce || return 0
  local mode
  mode="$(getenforce)"
  if [[ "$mode" == "Enforcing" ]]; then
    if ((SET_SELINUX_PERMISSIVE)); then
      warn "Explicit flag supplied: setting SELinux permissive for CloudStack setup. Review production SELinux policy requirements after installation."
      setenforce 0
      if [[ -f /etc/selinux/config ]]; then
        cp -a /etc/selinux/config "/etc/selinux/config.layersentry-backup.$(date +%Y%m%d-%H%M%S)"
        sed -ri 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config
      fi
    else
      die "SELinux is enforcing. This installer will not weaken host security implicitly. Configure appropriate CloudStack SELinux policy or rerun with --set-selinux-permissive if that is an approved design decision."
    fi
  fi
}

configure_repository() {
  case "$PKG_FAMILY" in
    apt)
      install -d -m 0755 /etc/apt/keyrings
      curl -fsSL --retry 3 https://download.cloudstack.org/release.asc -o "$TMP_DIR/cloudstack.asc"
      install -m 0644 "$TMP_DIR/cloudstack.asc" /etc/apt/keyrings/cloudstack.asc
      local base
      [[ "$OS_ID" == "debian" ]] && base="debian" || base="ubuntu"
      printf 'deb [signed-by=/etc/apt/keyrings/cloudstack.asc] https://download.cloudstack.org/%s %s %s\n' \
        "$base" "$OS_CODENAME" "$CLOUDSTACK_CHANNEL" > /etc/apt/sources.list.d/cloudstack.list
      apt-get update -y >>"$LOG_FILE" 2>&1
      ;;
    dnf)
      local repo_url="https://download.cloudstack.org/el/${OS_MAJOR}/${CLOUDSTACK_CHANNEL}/"
      curl -fsI --retry 3 "$repo_url" >/dev/null || die "CloudStack EL repository is unavailable for EL${OS_MAJOR}: $repo_url"
      cat > /etc/yum.repos.d/cloudstack.repo <<REPO
[cloudstack]
name=Apache CloudStack community packages ${CLOUDSTACK_CHANNEL}
baseurl=${repo_url}
enabled=1
gpgcheck=0
repo_gpgcheck=0
REPO
      dnf -q makecache --disablerepo='*' --enablerepo=cloudstack >>"$LOG_FILE" 2>&1
      ;;
    zypper)
      local repo_url="https://download.cloudstack.org/suse/${CLOUDSTACK_CHANNEL}/"
      curl -fsI --retry 3 "$repo_url" >/dev/null || die "The current CloudStack SUSE ${CLOUDSTACK_CHANNEL} community repository is unavailable; refusing to guess another path."
      zypper --non-interactive rr cloudstack >/dev/null 2>&1 || true
      zypper --non-interactive ar -f "$repo_url" cloudstack >>"$LOG_FILE" 2>&1
      zypper --non-interactive --gpg-auto-import-keys refresh cloudstack >>"$LOG_FILE" 2>&1
      ;;
  esac
}

verify_exact_package() {
  if [[ "$INSTALL_MODE" != "fresh" ]]; then
    return 0
  fi

  case "$PKG_FAMILY" in
    apt)
      local candidate
      candidate="$(apt-cache madison cloudstack-management | awk '{print $3}' | grep -E "(^|:)${CLOUDSTACK_VERSION}([+~.-]|$)" | head -1 || true)"
      [[ -n "$candidate" ]] || die "Exact CloudStack ${CLOUDSTACK_VERSION} management package is not available from the configured APT repository."
      info "Verified exact APT package candidate: cloudstack-management ${candidate}."
      ;;
    dnf)
      dnf -q --disablerepo='*' --enablerepo=cloudstack list --showduplicates cloudstack-management 2>/dev/null \
        | grep -F "${CLOUDSTACK_VERSION}-1" >/dev/null \
        || die "Exact CloudStack ${CLOUDSTACK_VERSION}-1 RPM is not available for EL${OS_MAJOR}."
      info "Verified exact RPM package candidate: ${CLOUDSTACK_VERSION}-1."
      ;;
    zypper)
      zypper --non-interactive se -s -r cloudstack cloudstack-management 2>/dev/null \
        | grep -F "$CLOUDSTACK_VERSION" >/dev/null \
        || die "Exact CloudStack ${CLOUDSTACK_VERSION} SUSE package is not available."
      info "Verified exact SUSE package candidate: ${CLOUDSTACK_VERSION}."
      ;;
  esac
}

install_dependencies() {
  [[ "$INSTALL_MODE" == "fresh" ]] || return 0
  case "$PKG_FAMILY" in
    apt)
      export DEBIAN_FRONTEND=noninteractive
      apt-get install -y openjdk-17-jre-headless mysql-server >>"$LOG_FILE" 2>&1
      ;;
    dnf)
      dnf install -y java-17-openjdk-headless mysql-server >>"$LOG_FILE" 2>&1
      ;;
    zypper)
      zypper --non-interactive install java-17-openjdk-headless mysql-server >>"$LOG_FILE" 2>&1
      ;;
  esac

  java -version 2>&1 | head -1 | grep -F '17' >/dev/null || die "Java 17 is not the active runtime after dependency installation."
}

install_cloudstack_packages() {
  [[ "$INSTALL_MODE" == "fresh" ]] || return 0
  case "$PKG_FAMILY" in
    apt)
      local mgmt_ver ui_ver
      mgmt_ver="$(apt-cache madison cloudstack-management | awk '{print $3}' | grep -E "(^|:)${CLOUDSTACK_VERSION}([+~.-]|$)" | head -1)"
      ui_ver="$(apt-cache madison cloudstack-ui | awk '{print $3}' | grep -E "(^|:)${CLOUDSTACK_VERSION}([+~.-]|$)" | head -1 || true)"
      export DEBIAN_FRONTEND=noninteractive
      if [[ -n "$ui_ver" ]]; then
        apt-get install -y "cloudstack-management=$mgmt_ver" "cloudstack-ui=$ui_ver" >>"$LOG_FILE" 2>&1
      else
        apt-get install -y "cloudstack-management=$mgmt_ver" >>"$LOG_FILE" 2>&1
      fi
      ;;
    dnf)
      dnf install -y "cloudstack-management-${CLOUDSTACK_VERSION}-1" "cloudstack-ui-${CLOUDSTACK_VERSION}-1" >>"$LOG_FILE" 2>&1
      ;;
    zypper)
      zypper --non-interactive install --oldpackage \
        "cloudstack-management=${CLOUDSTACK_VERSION}-1" "cloudstack-ui=${CLOUDSTACK_VERSION}-1" >>"$LOG_FILE" 2>&1
      ;;
  esac

  local current
  current="$(installed_cs_version)"
  [[ "$current" == "$CLOUDSTACK_VERSION" || "$current" == "$CLOUDSTACK_VERSION"-* || "$current" == *:"$CLOUDSTACK_VERSION"* ]] \
    || die "Installed CloudStack version '$current' does not match required ${CLOUDSTACK_VERSION}."
}

configure_local_mysql() {
  [[ "$INSTALL_MODE" == "fresh" && "$DB_HOST" == "localhost" ]] || return 0

  local mysql_service conf_dir conf_file
  case "$PKG_FAMILY" in
    apt) mysql_service="mysql"; conf_dir="/etc/mysql/conf.d" ;;
    dnf) mysql_service="mysqld"; conf_dir="/etc/my.cnf.d" ;;
    zypper) mysql_service="mysql"; conf_dir="/etc/my.cnf.d" ;;
  esac
  install -d -m 0755 "$conf_dir"
  conf_file="$conf_dir/cloudstack.cnf"
  if [[ -e "$conf_file" ]]; then
    cp -a "$conf_file" "${conf_file}.layersentry-backup.$(date +%Y%m%d-%H%M%S)"
  fi
  cat > "$conf_file" <<'MYSQLCONF'
[mysqld]
server_id=1
innodb_rollback_on_timeout=1
innodb_lock_wait_timeout=600
max_connections=350
log_bin=mysql-bin
binlog_format=ROW
MYSQLCONF
  systemctl enable "$mysql_service" >>"$LOG_FILE" 2>&1 || true
  systemctl restart "$mysql_service" >>"$LOG_FILE" 2>&1
  systemctl is-active --quiet "$mysql_service" || die "MySQL service '$mysql_service' is not active."
}

prompt_secret_if_needed() {
  local var_name="$1" prompt="$2"
  if [[ -z "${!var_name:-}" ]]; then
    if [[ ! -t 0 ]]; then
      die "$var_name is required in non-interactive mode. Set it in the environment; it will not be logged."
    fi
    local value
    read -r -s -p "$prompt" value
    printf '\n' >&2
    printf -v "$var_name" '%s' "$value"
  fi
}

configure_database() {
  [[ "$INSTALL_MODE" == "fresh" ]] || return 0

  prompt_secret_if_needed LAYERSENTRY_CLOUD_DB_PASSWORD "CloudStack database-user password: "
  [[ -n "${LAYERSENTRY_CLOUD_DB_PASSWORD:-}" ]] || die "CloudStack database password must not be empty."

  if [[ "$DB_HOST" == "localhost" ]]; then
    if command_exists mysql && mysql -NBe "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='cloud'" 2>/dev/null | grep -qx cloud; then
      die "A database named 'cloud' already exists. Refusing to initialize or recreate it automatically. Use --branding-only for an existing CloudStack installation."
    fi
  fi

  local deploy_arg
  if [[ -n "${LAYERSENTRY_DB_DEPLOY_PASSWORD:-}" ]]; then
    deploy_arg="--deploy-as=${DB_DEPLOY_USER}:${LAYERSENTRY_DB_DEPLOY_PASSWORD}"
  else
    if [[ "$DB_HOST" != "localhost" ]]; then
      prompt_secret_if_needed LAYERSENTRY_DB_DEPLOY_PASSWORD "Database administrative password for ${DB_DEPLOY_USER}@${DB_HOST}: "
      deploy_arg="--deploy-as=${DB_DEPLOY_USER}:${LAYERSENTRY_DB_DEPLOY_PASSWORD}"
    else
      deploy_arg="--deploy-as=${DB_DEPLOY_USER}"
    fi
  fi

  # Do not echo this command: it contains a database password by design of the official setup tool.
  cloudstack-setup-databases \
    "cloud:${LAYERSENTRY_CLOUD_DB_PASSWORD}@${DB_HOST}" \
    "$deploy_arg" \
    -i "$PRIMARY_IP" >>"$LOG_FILE" 2>&1

  unset LAYERSENTRY_CLOUD_DB_PASSWORD LAYERSENTRY_DB_DEPLOY_PASSWORD || true
}

configure_management() {
  [[ "$INSTALL_MODE" == "fresh" ]] || return 0
  cloudstack-setup-management >>"$LOG_FILE" 2>&1
}

prepare_kvm() {
  ((WITH_KVM)) || return 0

  grep -Eq '(vmx|svm)' /proc/cpuinfo || die "--with-kvm requested but CPU virtualization extensions are not exposed. On a VM, enable nested virtualization first."
  [[ -e /dev/kvm ]] || die "--with-kvm requested but /dev/kvm is unavailable."

  case "$PKG_FAMILY" in
    apt)
      local agent_ver
      agent_ver="$(apt-cache madison cloudstack-agent | awk '{print $3}' | grep -E "(^|:)${CLOUDSTACK_VERSION}([+~.-]|$)" | head -1 || true)"
      [[ -n "$agent_ver" ]] || die "Exact cloudstack-agent ${CLOUDSTACK_VERSION} package is unavailable."
      apt-get install -y "cloudstack-agent=$agent_ver" >>"$LOG_FILE" 2>&1
      ;;
    dnf)
      dnf install -y "cloudstack-agent-${CLOUDSTACK_VERSION}-1" >>"$LOG_FILE" 2>&1
      ;;
    zypper)
      zypper --non-interactive install --oldpackage "cloudstack-agent=${CLOUDSTACK_VERSION}-1" >>"$LOG_FILE" 2>&1
      ;;
  esac

  warn "KVM agent installed, but bridge/VLAN/storage/libvirt security configuration was intentionally NOT guessed. Complete host networking and libvirt preparation from the CloudStack 4.22 KVM guide before adding this host."
}

package_file_list() {
  case "$PKG_FAMILY" in
    apt)
      dpkg -L cloudstack-ui 2>/dev/null || true
      dpkg -L cloudstack-management 2>/dev/null || true
      ;;
    dnf|zypper)
      rpm -ql cloudstack-ui 2>/dev/null || true
      rpm -ql cloudstack-management 2>/dev/null || true
      ;;
  esac
}

find_ui_root() {
  local candidates=()
  while IFS= read -r p; do
    [[ "$p" == */index.html ]] || continue
    if [[ -f "$p" ]] && grep -Eq 'id=.*(app|root)' "$p" 2>/dev/null; then
      candidates+=("$(dirname "$p")")
    fi
  done < <(package_file_list)

  if ((${#candidates[@]} == 0)); then
    while IFS= read -r p; do
      candidates+=("$(dirname "$p")")
    done < <(find /usr/share /var/lib -maxdepth 6 -type f -name index.html 2>/dev/null \
      | grep -E 'cloudstack|client' | head -10)
  fi

  ((${#candidates[@]} > 0)) || die "Unable to locate the installed CloudStack UI root. No arbitrary web path will be modified."
  UI_ROOT="${candidates[0]}"
  ASSETS_DIR="$UI_ROOT/assets"
  install -d -m 0755 "$ASSETS_DIR"
  info "Detected CloudStack UI root: $UI_ROOT"
}

find_config_file() {
  local c
  for c in \
    /etc/cloudstack/management/config.json \
    /etc/cloudstack/ui/config.json \
    "$UI_ROOT/config.json"; do
    if [[ -f "$c" || -L "$c" ]]; then
      CONFIG_FILE="$c"
      break
    fi
  done

  if [[ -z "$CONFIG_FILE" ]]; then
    c="$(package_file_list | grep -E '/config\.json$' | head -1 || true)"
    [[ -n "$c" && -e "$c" ]] && CONFIG_FILE="$c"
  fi
  [[ -n "$CONFIG_FILE" ]] || die "Unable to locate CloudStack UI config.json. Refusing to assume a version-specific path."
  CONFIG_FILE="$(readlink -f "$CONFIG_FILE")"
  info "Detected CloudStack UI config: $CONFIG_FILE"
}

download_verified() {
  local url="$1" expected="$2" out="$3"
  curl -fsSL --retry 3 "$url" -o "$out"
  printf '%s  %s\n' "$expected" "$out" | sha256sum -c - >/dev/null \
    || die "Integrity check failed for branding asset: $url"
}

apply_config_patch() {
  local backup="${CONFIG_FILE}.layersentry-backup.$(date +%Y%m%d-%H%M%S)"
  cp -a "$CONFIG_FILE" "$backup"

  python3 - "$CONFIG_FILE" <<'PY'
import json, sys
path = sys.argv[1]
with open(path, encoding='utf-8') as f:
    cfg = json.load(f)

cfg['appTitle'] = 'Layersentry'
cfg['loginTitle'] = 'Layersentry'
cfg['loginFavicon'] = 'assets/layersentry-icon.svg'
cfg['loginFooter'] = 'Secure cloud infrastructure management.'
cfg['logo'] = 'assets/layersentry-logo.svg'
cfg['minilogo'] = 'assets/layersentry-icon.svg'
cfg['banner'] = 'assets/layersentry-logo.svg'
cfg['favicon'] = 'assets/layersentry-icon.svg'
cfg['docBase'] = 'https://docs.cloudstack.apache.org/en/4.22.1.1'
cfg['footer'] = "Layersentry &middot; Apache CloudStack is licensed under the <a href='https://www.apache.org/licenses/LICENSE-2.0' target='_blank' rel='noopener noreferrer'>Apache License, Version 2.0</a>."

theme = cfg.setdefault('theme', {})
theme.update({
    '@layout-mode': 'light',
    '@logo-background-color': '#ffffff',
    '@mini-logo-background-color': '#ffffff',
    '@navigation-background-color': '#071536',
    '@project-nav-background-color': '#071536',
    '@project-nav-text-color': 'rgba(255, 255, 255, 0.82)',
    '@navigation-text-color': 'rgba(255, 255, 255, 0.82)',
    '@primary-color': '#1849b5',
    '@link-color': '#1849b5',
    '@link-hover-color': '#123a91',
    '@loading-color': '#1849b5',
    '@processing-color': '#1849b5',
    '@success-color': '#14804a',
    '@warning-color': '#b54708',
    '@error-color': '#b42318',
    '@heading-color': '#101828',
    '@text-color': '#344054',
    '@text-color-secondary': '#667085',
    '@disabled-color': '#98a2b3',
    '@border-color-base': '#d0d5dd',
    '@border-radius-base': '6px',
    '@box-shadow-base': '0 1px 3px rgba(16, 24, 40, 0.10)',
    '@logo-width': '192px',
    '@logo-height': '64px',
    '@mini-logo-width': '44px',
    '@mini-logo-height': '52px',
    '@banner-width': '300px',
    '@banner-height': '100px'
})

with open(path, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
    f.write('\n')
PY
  python3 -m json.tool "$CONFIG_FILE" >/dev/null
  chmod 0644 "$CONFIG_FILE"
  info "Backed up original UI configuration to $backup"
}

inject_stylesheet() {
  local index="$UI_ROOT/index.html"
  [[ -f "$index" ]] || die "CloudStack UI index.html not found at $index"
  if ! grep -Fq 'assets/layersentry.css' "$index"; then
    cp -a "$index" "${index}.layersentry-backup.$(date +%Y%m%d-%H%M%S)"
    python3 - "$index" <<'PY'
import sys
p=sys.argv[1]
s=open(p, encoding='utf-8').read()
link='<link rel="stylesheet" href="assets/layersentry.css">'
if '</head>' not in s:
    raise SystemExit('index.html has no </head>; refusing unsafe injection')
s=s.replace('</head>', f'  {link}\n</head>', 1)
open(p,'w',encoding='utf-8').write(s)
PY
  fi
  grep -Fq 'assets/layersentry.css' "$index" || die "Layersentry stylesheet reference was not installed."
}

apply_branding() {
  find_ui_root
  find_config_file

  download_verified "$ASSET_BASE_URL/assets/layersentry-logo.svg" "$LOGO_SHA256" "$TMP_DIR/layersentry-logo.svg"
  download_verified "$ASSET_BASE_URL/assets/layersentry-icon.svg" "$ICON_SHA256" "$TMP_DIR/layersentry-icon.svg"
  download_verified "$SOURCE_BASE_URL/src/style/layersentry.less" "$STYLE_SHA256" "$TMP_DIR/layersentry.css"

  install -m 0644 "$TMP_DIR/layersentry-logo.svg" "$ASSETS_DIR/layersentry-logo.svg"
  install -m 0644 "$TMP_DIR/layersentry-icon.svg" "$ASSETS_DIR/layersentry-icon.svg"
  install -m 0644 "$TMP_DIR/layersentry.css" "$ASSETS_DIR/layersentry.css"

  apply_config_patch
  inject_stylesheet
}

restart_services() {
  systemctl restart cloudstack-management >>"$LOG_FILE" 2>&1
  systemctl is-active --quiet cloudstack-management || die "cloudstack-management is not active after restart."

  if ((WITH_KVM)); then
    systemctl restart cloudstack-agent >>"$LOG_FILE" 2>&1 || true
    systemctl is-active --quiet cloudstack-agent || warn "cloudstack-agent is not active yet; complete KVM host preparation before registration."
  fi
}

health_check() {
  local url="http://127.0.0.1:8080/client/" code="" i
  for i in $(seq 1 36); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 3 --max-time 5 "$url" || true)"
    if [[ "$code" == "200" || "$code" == "302" || "$code" == "401" ]]; then
      info "CloudStack web endpoint responded with HTTP $code."
      return 0
    fi
    sleep 5
  done
  die "CloudStack management service is active but $url did not return an expected HTTP response. Last HTTP code: ${code:-none}."
}

main() {
  parse_args "$@"
  require_root
  init_logging
  log_raw "${PRODUCT_NAME} installer for Apache CloudStack ${CLOUDSTACK_VERSION} LTS"
  log_raw "Log: $LOG_FILE"

  progress 5 "Pre-flight checks"
  [[ -r /etc/os-release ]] || die "Linux /etc/os-release is required."

  progress 10 "Detecting supported operating system"
  detect_os
  install_bootstrap_tools
  detect_install_mode
  check_resources
  check_selinux

  progress 20 "Configuring package repositories"
  if [[ "$INSTALL_MODE" == "fresh" ]]; then
    configure_repository
    verify_exact_package
  else
    info "Branding-update mode: package repository and database changes are skipped."
  fi

  progress 35 "Installing dependencies"
  install_dependencies

  progress 50 "Installing CloudStack management services"
  install_cloudstack_packages
  prepare_kvm

  progress 65 "Configuring database"
  configure_local_mysql
  configure_database

  progress 75 "Configuring management server"
  configure_management

  progress 85 "Applying Layersentry branding"
  apply_branding

  progress 92 "Starting services"
  restart_services

  progress 97 "Running health checks"
  health_check

  progress 100 "Layersentry installation completed"
  log_raw "Access URL: http://${PRIMARY_IP}:8080/client/"
  log_raw "CloudStack internal package/service/API names were preserved."
  log_raw "Review firewall exposure: management ports 8096 and 8250 must not be publicly accessible."
  if ((WITH_KVM)); then
    log_raw "KVM note: complete documented bridge/libvirt/storage preparation before adding this host to CloudStack."
  fi
}

main "$@"

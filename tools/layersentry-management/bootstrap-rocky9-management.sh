#!/usr/bin/env bash
set -Eeuo pipefail

# LayerSentry Rocky Linux 9 CloudStack management-node bootstrap.
# Database creation/failover is deliberately outside this node-local tool.

readonly PROGRAM=${0##*/}
ACTION=${1:-apply}
ROOT=${LAYERSENTRY_ROOT:-}
ETC="${ROOT}/etc"
STATE_DIR="${ROOT}/var/lib/layersentry/management-bootstrap"
BACKUP_DIR="${STATE_DIR}/rollback"
DB_TARGET="${ETC}/cloudstack/management/db.properties"
KEY_TARGET="${ETC}/cloudstack/management/key"
DEFAULT_TARGET="${ETC}/default/cloudstack-management"

log() { printf '%s\n' "$*" >&2; }
die() { log "ERROR: $*"; exit 1; }
run() {
  if [[ ${LAYERSENTRY_DRY_RUN:-0} == 1 ]]; then
    printf 'DRY-RUN:' >&2; printf ' %q' "$@" >&2; printf '\n' >&2
  else
    "$@"
  fi
}
install_config() {
  local mode=$1 owner=$2 group=$3 source=$4 target=$5
  if [[ -n $ROOT ]]; then
    run install -D -m "$mode" "$source" "$target"
  else
    run install -D -o "$owner" -g "$group" -m "$mode" "$source" "$target"
  fi
}
need() { command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"; }

validate_source() {
  local source=$1 label=$2 mode
  [[ -f $source && ! -L $source ]] || die "$label must be a regular, non-symlink file"
  mode=$(stat -c '%a' "$source")
  (( 8#$mode <= 8#600 )) || die "$label permissions must be 0600 or stricter (found $mode)"
}

preflight() {
  [[ $EUID -eq 0 || -n $ROOT ]] || die "run as root"
  [[ $ACTION =~ ^(apply|preflight|status)$ ]] || die "usage: $PROGRAM [apply|preflight|status]"
  : "${LAYERSENTRY_PACKAGE_NEVRA:?set exact CloudStack management package NEVRA}"
  [[ $LAYERSENTRY_PACKAGE_NEVRA =~ ^cloudstack-management-[0-9][A-Za-z0-9._+~-]*\.(x86_64|noarch)$ ]] ||
    die "LAYERSENTRY_PACKAGE_NEVRA must be an exact cloudstack-management NEVRA"
  : "${LAYERSENTRY_DB_PROPERTIES_FILE:?set path to encrypted db.properties}"
  validate_source "$LAYERSENTRY_DB_PROPERTIES_FILE" "db.properties input"
  if [[ -n ${LAYERSENTRY_ENCRYPTION_KEY_FILE:-} ]]; then
    validate_source "$LAYERSENTRY_ENCRYPTION_KEY_FILE" "encryption key input"
  fi
  if [[ -n ${LAYERSENTRY_MANAGEMENT_DEFAULT_FILE:-} ]]; then
    validate_source "$LAYERSENTRY_MANAGEMENT_DEFAULT_FILE" "management defaults input"
  fi
  if [[ -n ${LAYERSENTRY_REPO_FILE:-} ]]; then
    validate_source "$LAYERSENTRY_REPO_FILE" "repository input"
    grep -Eiq '^[[:space:]]*gpgcheck[[:space:]]*=[[:space:]]*1([[:space:]]*)$' "$LAYERSENTRY_REPO_FILE" ||
      die "repository input must enable gpgcheck=1"
    ! grep -Eiq '^[[:space:]]*(gpgcheck|repo_gpgcheck)[[:space:]]*=[[:space:]]*0' "$LAYERSENTRY_REPO_FILE" ||
      die "repository input disables signature verification"
  fi
  if [[ -z $ROOT ]]; then
    need dnf; need rpm; need systemctl; need firewall-cmd; need getenforce; need curl
    grep -Eq '^ID=("?)(rocky)\1$' /etc/os-release || die "Rocky Linux is required"
    grep -Eq '^VERSION_ID=("?)9([.]?[0-9]*)?\1$' /etc/os-release || die "Rocky Linux 9 is required"
    [[ $(getenforce) == Enforcing ]] || die "SELinux must be enforcing"
    systemctl is-active --quiet firewalld || die "firewalld must be active"
  fi
  [[ -n ${LAYERSENTRY_FIREWALL_PORTS:-} ]] || die "set explicit LAYERSENTRY_FIREWALL_PORTS (for example 8080/tcp,8250/tcp)"
}

backup_one() {
  local target=$1 name=${1##*/}
  if [[ -e $target ]]; then
    run rm -f "${BACKUP_DIR}/${name}.absent"
    run install -D -m 0600 "$target" "${BACKUP_DIR}/${name}"
  else
    run rm -f "${BACKUP_DIR}/${name}"
    run touch "${BACKUP_DIR}/${name}.absent"
  fi
}

restore() {
  local name target
  [[ -d $BACKUP_DIR ]] || return 0
  for name in db.properties key cloudstack-management layersentry-cloudstack.repo; do
    case $name in
      db.properties) target=$DB_TARGET ;;
      key) target=$KEY_TARGET ;;
      cloudstack-management) target=$DEFAULT_TARGET ;;
      *) target="${ETC}/yum.repos.d/$name" ;;
    esac
    if [[ -f ${BACKUP_DIR}/${name}.absent ]]; then
      run rm -f "$target"
    elif [[ -f ${BACKUP_DIR}/${name} ]]; then
      run install -D -m 0600 "${BACKUP_DIR}/${name}" "$target"
    fi
  done
}

on_error() {
  local rc=$?
  log "bootstrap failed; restoring node-local configuration backup"
  restore || true
  [[ -n $ROOT ]] || systemctl restart cloudstack-management >/dev/null 2>&1 || true
  exit "$rc"
}

status() {
  if [[ -f ${STATE_DIR}/applied ]]; then
    log "configuration marker: applied"
  else
    log "configuration marker: absent"
  fi
  [[ -n $ROOT ]] || systemctl --no-pager --full status cloudstack-management
}

apply() {
  trap on_error ERR
  run install -d -m 0700 "$STATE_DIR" "$BACKUP_DIR"
  backup_one "$DB_TARGET"
  backup_one "$KEY_TARGET"
  backup_one "$DEFAULT_TARGET"
  [[ -n ${LAYERSENTRY_REPO_FILE:-} ]] && backup_one "${ETC}/yum.repos.d/layersentry-cloudstack.repo"

  if [[ -n ${LAYERSENTRY_REPO_FILE:-} ]]; then
    run install -D -m 0644 "$LAYERSENTRY_REPO_FILE" "${ETC}/yum.repos.d/layersentry-cloudstack.repo"
  fi
  if [[ -z $ROOT ]]; then
    run dnf --assumeyes --setopt=install_weak_deps=False install "$LAYERSENTRY_PACKAGE_NEVRA"
    [[ $(rpm -q --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}' cloudstack-management) == "$LAYERSENTRY_PACKAGE_NEVRA" ]] ||
      die "installed management package does not match requested NEVRA"
  fi

  install_config 0640 root cloud "$LAYERSENTRY_DB_PROPERTIES_FILE" "$DB_TARGET"
  [[ -z ${LAYERSENTRY_ENCRYPTION_KEY_FILE:-} ]] ||
    install_config 0640 root cloud "$LAYERSENTRY_ENCRYPTION_KEY_FILE" "$KEY_TARGET"
  [[ -z ${LAYERSENTRY_MANAGEMENT_DEFAULT_FILE:-} ]] ||
    install_config 0644 root root "$LAYERSENTRY_MANAGEMENT_DEFAULT_FILE" "$DEFAULT_TARGET"

  if [[ -z $ROOT ]]; then
    local port
    IFS=',' read -r -a ports <<<"$LAYERSENTRY_FIREWALL_PORTS"
    for port in "${ports[@]}"; do
      [[ $port =~ ^[0-9]{1,5}/(tcp|udp)$ ]] || die "invalid firewall port: $port"
      (( ${port%/*} >= 1 && ${port%/*} <= 65535 )) || die "firewall port out of range: $port"
      firewall-cmd --permanent --query-port="$port" >/dev/null || run firewall-cmd --permanent --add-port="$port"
    done
    run firewall-cmd --reload
    run restorecon -RF "$DB_TARGET" "${ETC}/cloudstack/management" "$DEFAULT_TARGET"
    run systemctl enable cloudstack-management
    run systemctl restart cloudstack-management
    if [[ ${LAYERSENTRY_DRY_RUN:-0} != 1 ]]; then
      local deadline=$((SECONDS + ${LAYERSENTRY_STARTUP_TIMEOUT_SECONDS:-300}))
      until curl --fail --silent --show-error --max-time 5 http://127.0.0.1:8080/client/ >/dev/null; do
        (( SECONDS < deadline )) || die "management UI did not become reachable before timeout"
        sleep 5
      done
      systemctl is-active --quiet cloudstack-management || die "cloudstack-management is not active"
    fi
  fi
  run touch "${STATE_DIR}/applied"
  trap - ERR
  log "management-node bootstrap applied"
}

preflight
case $ACTION in
  apply) apply ;;
  preflight) log "preflight passed" ;;
  status) status ;;
esac

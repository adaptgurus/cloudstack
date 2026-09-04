#!/usr/bin/env bash
# Layersentry V1.0 recovery/resume installer for Rocky Linux 9.
# This script is intentionally scoped to an interrupted exact CloudStack 4.22.1.1
# installation where RPM installation succeeded but the Layersentry UI build or a
# later configuration stage failed. It never installs/downgrades CloudStack RPMs
# and never creates KVM bridges, VLANs or storage pools.

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly PRODUCT='Layersentry'
readonly PRODUCT_VERSION='V1.0'
readonly CLOUDSTACK_VERSION='4.22.1.1'
readonly CLOUDSTACK_RELEASE='1'
readonly UI_COMMIT='6d364150095ba5cfd433746dca1f13d38ca1951f'
readonly UI_REPOSITORY='https://github.com/adaptgurus/cloudstack.git'
readonly EXPECTED_FQDN='layersentry.lab.example'
readonly EXPECTED_IP='10.10.10.14'
readonly LOG_FILE="/var/log/layersentry-rocky9-resume-$(date +%Y%m%d-%H%M%S).log"

WORK_DIR=''
SOURCE_DIR=''
UI_ROOT=''
MYSQL_MODE=''
SECRETS_FILE=''
CURRENT_STAGE='initialization'

log() { printf '%s\n' "$*" | tee -a "$LOG_FILE"; }
info() { log "INFO: $*"; }
warn() { log "WARN: $*"; }
die() { log "ERROR: $*" >&2; exit 1; }
stage() { CURRENT_STAGE="$1"; log "==> $CURRENT_STAGE"; }

on_error() {
  local rc=$?
  set +e
  printf 'ERROR: %s resume failed during %s (line %s, exit %s).\n' \
    "$PRODUCT" "$CURRENT_STAGE" "${BASH_LINENO[0]:-unknown}" "$rc" | tee -a "$LOG_FILE" >&2
  exit "$rc"
}
cleanup() {
  [[ -z "${WORK_DIR:-}" || ! -d "$WORK_DIR" ]] || rm -rf -- "$WORK_DIR"
}
trap on_error ERR
trap cleanup EXIT

require_root() {
  [[ $EUID -eq 0 ]] || die 'Run this script as root.'
}

version_is_exact() {
  [[ "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" ||
     "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}."* ]]
}

validate_host() {
  stage 'validating exact partial installation'
  . /etc/os-release
  [[ "${ID:-}" == 'rocky' && "${VERSION_ID%%.*}" == '9' ]] \
    || die "Rocky Linux 9 is required; detected ${PRETTY_NAME:-unknown}."
  [[ "$(uname -m)" == 'x86_64' ]] || die 'x86_64 is required.'

  local management ui agent primary_ip fqdn
  management="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-management 2>/dev/null || true)"
  ui="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-ui 2>/dev/null || true)"
  agent="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-agent 2>/dev/null || true)"
  version_is_exact "$management" || die "Expected cloudstack-management ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}; found ${management:-not-installed}."
  version_is_exact "$ui" || die "Expected cloudstack-ui ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}; found ${ui:-not-installed}."
  version_is_exact "$agent" || die "Expected cloudstack-agent ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}; found ${agent:-not-installed}."

  rpm -q mysql-server >/dev/null 2>&1 || die 'mysql-server is missing from the interrupted installation.'
  java -version 2>&1 | head -1 | grep -E 'version "17([.]|\")' >/dev/null \
    || die 'Java 17 is not the active Java runtime.'

  grep -Eq '(vmx|svm)' /proc/cpuinfo || die 'CPU virtualization extensions are not exposed.'
  [[ -c /dev/kvm ]] || die '/dev/kvm is missing.'

  primary_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1);exit}}')"
  [[ "$primary_ip" == "$EXPECTED_IP" ]] || die "Expected management IP $EXPECTED_IP; detected ${primary_ip:-none}."
  fqdn="$(hostname -f 2>/dev/null || true)"
  [[ "$fqdn" == "$EXPECTED_FQDN" ]] || die "Expected FQDN $EXPECTED_FQDN; detected ${fqdn:-none}."

  info "Exact CloudStack packages present: management=$management ui=$ui agent=$agent."
  info "Host identity verified: $EXPECTED_FQDN / $EXPECTED_IP; /dev/kvm present."
}

prepare_build_tools() {
  stage 'preparing build/runtime prerequisites'
  dnf -y install ca-certificates curl git openssl python3 rsync tar gzip jq which \
    gcc-c++ make nodejs npm nfs-utils firewalld >>"$LOG_FILE" 2>&1
  local node_major
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$node_major" =~ ^[0-9]+$ && "$node_major" -ge 16 ]] \
    || die "Node.js 16 or newer is required; detected $(node --version 2>/dev/null || echo none)."
  info "Build runtime: Node.js $(node --version), npm $(npm --version)."
}

build_ui() {
  stage 'building Layersentry UI without stale upstream lockfile'
  WORK_DIR="$(mktemp -d /var/tmp/layersentry-rocky9-resume.XXXXXX)"
  SOURCE_DIR="$WORK_DIR/source"
  git init -q "$SOURCE_DIR"
  git -C "$SOURCE_DIR" remote add origin "$UI_REPOSITORY"
  git -C "$SOURCE_DIR" config core.sparseCheckout true
  printf 'ui/\n' >"$SOURCE_DIR/.git/info/sparse-checkout"
  git -C "$SOURCE_DIR" -c protocol.version=2 fetch -q --depth 1 --filter=blob:none origin "$UI_COMMIT"
  git -C "$SOURCE_DIR" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" == "$UI_COMMIT" ]] \
    || die 'UI source provenance verification failed.'

  pushd "$SOURCE_DIR/ui" >/dev/null
  export NODE_OPTIONS='--openssl-legacy-provider --max-old-space-size=4096'
  export npm_config_python=/usr/bin/python3

  # The reviewed branch currently carries a package-lock generated for an older
  # dependency graph (its root version is 4.19 while package.json is 4.22-era).
  # npm ci therefore fails correctly. This temporary worktree deliberately ignores
  # that stale lock and resolves only from the pinned package.json; no lockfile is
  # modified in the repository.
  rm -rf node_modules
  rm -f package-lock.json
  npm install --legacy-peer-deps --no-audit --no-fund --package-lock=false >>"$LOG_FILE" 2>&1
  npm run build >>"$LOG_FILE" 2>&1
  popd >/dev/null

  [[ -f "$SOURCE_DIR/ui/dist/index.html" ]] || die 'UI build did not produce dist/index.html.'
  [[ -f "$SOURCE_DIR/ui/dist/config.json" ]] || die 'UI build did not produce dist/config.json.'
  grep -Rqs --include='*.js' 'DBaaS' "$SOURCE_DIR/ui/dist" || die 'Compiled UI does not contain DBaaS.'
  grep -Rqs --include='*.js' 'APaaS' "$SOURCE_DIR/ui/dist" || die 'Compiled UI does not contain APaaS.'

  python3 - "$SOURCE_DIR/ui/dist/config.json" <<'PY'
import json, sys
p=sys.argv[1]
with open(p, encoding='utf-8') as f: c=json.load(f)
c['appTitle']='Layersentry'
c['loginTitle']='Layersentry'
c['loginFooter']='Secure cloud infrastructure management.'
c['footer']='Layersentry V1.0'
c['notifyLatestCSVersion']=False
c['apidocs']=False
if isinstance(c.get('userCard'), dict): c['userCard']['enabled']=False
with open(p,'w',encoding='utf-8') as f:
    json.dump(c,f,indent=2,ensure_ascii=False); f.write('\n')
PY
  python3 -m json.tool "$SOURCE_DIR/ui/dist/config.json" >/dev/null
  info "Production UI build passed for pinned source $UI_COMMIT; DBaaS/APaaS verified."
}

configure_mysql() {
  stage 'configuring MySQL safely'
  install -d -m 0755 /etc/my.cnf.d
  if [[ -e /etc/my.cnf.d/cloudstack.cnf ]]; then
    cp -a /etc/my.cnf.d/cloudstack.cnf "/etc/my.cnf.d/cloudstack.cnf.layersentry-backup.$(date +%Y%m%d-%H%M%S)"
  fi
  cat >/etc/my.cnf.d/cloudstack.cnf <<'EOF'
[mysqld]
server_id=1
innodb_rollback_on_timeout=1
innodb_lock_wait_timeout=600
max_connections=350
log_bin=mysql-bin
binlog_format=ROW
EOF
  chmod 0644 /etc/my.cnf.d/cloudstack.cnf
  systemctl enable --now mysqld >>"$LOG_FILE" 2>&1
  systemctl restart mysqld >>"$LOG_FILE" 2>&1
  systemctl is-active --quiet mysqld || die 'mysqld is not active.'

  if mysql --protocol=socket -uroot -NBe 'SELECT 1' >/dev/null 2>&1; then
    MYSQL_MODE='socket'
  else
    die 'Local MySQL root socket authentication is unavailable; refusing to guess credentials during automated recovery.'
  fi
}

mysql_query() { mysql --protocol=socket -uroot -NBe "$1"; }

database_complete() {
  local cloud usage
  cloud="$(mysql_query "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='cloud'" 2>/dev/null || echo 0)"
  usage="$(mysql_query "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='cloud_usage'" 2>/dev/null || echo 0)"
  [[ "$cloud" =~ ^[0-9]+$ && "$usage" =~ ^[0-9]+$ ]] || return 1
  ((cloud >= 50 && usage >= 1))
}

configure_database() {
  stage 'configuring CloudStack database idempotently'
  if mysql_query "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='cloud'" 2>/dev/null | grep -Fxq cloud; then
    database_complete || die "Existing 'cloud' database is incomplete/unknown; refusing destructive recovery."
    info 'Existing CloudStack databases look complete; preserving them.'
    return 0
  fi

  local db_password
  db_password="$(openssl rand -hex 24)"
  SECRETS_FILE="/root/layersentry-secrets-$(date +%Y%m%d-%H%M%S).env"
  {
    printf '# Root-only Layersentry database credential.\n'
    printf 'LAYERSENTRY_CLOUD_DB_PASSWORD=%q\n' "$db_password"
    printf 'LAYERSENTRY_UI_COMMIT=%q\n' "$UI_COMMIT"
    printf 'CLOUDSTACK_VERSION=%q\n' "$CLOUDSTACK_VERSION"
  } >"$SECRETS_FILE"
  chmod 0600 "$SECRETS_FILE"

  # Do not echo the command because it carries the generated DB password.
  cloudstack-setup-databases "cloud:${db_password}@localhost" --deploy-as=root -i "$EXPECTED_IP" >>"$LOG_FILE" 2>&1
  unset db_password
  database_complete || die 'CloudStack database setup returned, but expected schemas/tables are not complete.'
  info "CloudStack database initialized; credential stored only in $SECRETS_FILE."
}

configure_management() {
  stage 'configuring CloudStack management service'
  cloudstack-setup-management >>"$LOG_FILE" 2>&1
}

find_ui_root() {
  local index
  index="$(rpm -ql cloudstack-ui 2>/dev/null | awk '/\/index\.html$/ {print; exit}')"
  [[ -n "$index" && -f "$index" ]] || die 'Unable to locate cloudstack-ui index.html.'
  UI_ROOT="$(dirname "$index")"
}

deploy_ui() {
  stage 'deploying Layersentry UI with backup'
  find_ui_root
  local stamp backup config_target
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup="/var/backups/layersentry/${stamp}/cloudstack-ui-before-layersentry.tar.gz"
  install -d -m 0700 "$(dirname "$backup")"
  tar --xattrs --acls -C "$UI_ROOT" -czf "$backup" .
  chmod 0600 "$backup"

  config_target="$(readlink -f "$UI_ROOT/config.json" 2>/dev/null || true)"
  [[ -n "$config_target" ]] || config_target='/etc/cloudstack/management/config.json'

  systemctl stop cloudstack-management >>"$LOG_FILE" 2>&1 || true
  rsync -a --exclude='config.json' --chown=root:root --chmod=D755,F644 "$SOURCE_DIR/ui/dist/" "$UI_ROOT/"
  install -D -m 0644 -o root -g root "$SOURCE_DIR/ui/dist/config.json" "$config_target"
  restorecon -RF "$UI_ROOT" "$config_target" >>"$LOG_FILE" 2>&1 || true
  info "Layersentry UI deployed; backup: $backup."
}

configure_firewall() {
  stage 'configuring local firewall'
  if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=ssh >>"$LOG_FILE" 2>&1
    firewall-cmd --permanent --add-port=8080/tcp >>"$LOG_FILE" 2>&1
    firewall-cmd --reload >>"$LOG_FILE" 2>&1
  else
    firewall-offline-cmd --add-service=ssh >>"$LOG_FILE" 2>&1
    firewall-offline-cmd --add-port=8080/tcp >>"$LOG_FILE" 2>&1
    systemctl enable --now firewalld >>"$LOG_FILE" 2>&1
  fi
  firewall-cmd --query-service=ssh >/dev/null || die 'SSH is not permitted by firewalld.'
  firewall-cmd --query-port=8080/tcp >/dev/null || die 'TCP/8080 is not permitted by firewalld.'
}

start_services() {
  stage 'starting and validating Layersentry services'
  systemctl enable cloudstack-management >>"$LOG_FILE" 2>&1
  systemctl restart cloudstack-management >>"$LOG_FILE" 2>&1
  systemctl is-active --quiet cloudstack-management || die 'cloudstack-management is not active.'

  systemctl enable cloudstack-agent >>"$LOG_FILE" 2>&1 || true
  systemctl restart cloudstack-agent >>"$LOG_FILE" 2>&1 || true
  systemctl is-active --quiet cloudstack-agent || warn 'cloudstack-agent is not active yet; cloudbr0/libvirt host networking is still pending.'

  local code='' attempt
  for attempt in $(seq 1 60); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 3 --max-time 8 http://127.0.0.1:8080/client/ || true)"
    case "$code" in 200|302|401) break ;; esac
    sleep 5
  done
  case "$code" in 200|302|401) ;; *) die "UI health check failed; last HTTP code ${code:-none}." ;; esac
  info "Layersentry endpoint healthy with HTTP $code."
}

final_evidence() {
  stage 'final evidence'
  rpm -q cloudstack-management cloudstack-ui cloudstack-agent | tee -a "$LOG_FILE"
  java -version 2>&1 | head -3 | tee -a "$LOG_FILE"
  systemctl is-active mysqld cloudstack-management | tee -a "$LOG_FILE"
  systemctl is-active cloudstack-agent 2>&1 | tee -a "$LOG_FILE" || true
  virsh -c qemu:///system list --all 2>&1 | tee -a "$LOG_FILE" || true
  ip -4 -br addr | tee -a "$LOG_FILE"
  ip route | tee -a "$LOG_FILE"
  log '[100%] Layersentry V1.0 resumed installation completed'
  log "Access URL: http://${EXPECTED_IP}:8080/client/"
  [[ -z "$SECRETS_FILE" ]] || log "Database credential file: $SECRETS_FILE (root-only)"
  log 'DBaaS/APaaS catalogs are compiled; provisioning remains disabled until backend integration exists.'
  log 'KVM package/runtime is installed; cloudbr0, guest/public networking and storage remain intentionally unconfigured.'
}

main() {
  require_root
  touch "$LOG_FILE"; chmod 0600 "$LOG_FILE"
  log "$PRODUCT $PRODUCT_VERSION Rocky Linux 9 safe resume"
  log "Log: $LOG_FILE"
  validate_host
  prepare_build_tools
  build_ui
  configure_mysql
  configure_database
  configure_management
  deploy_ui
  configure_firewall
  start_services
  final_evidence
}
main "$@"

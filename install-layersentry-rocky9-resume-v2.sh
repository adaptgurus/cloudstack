#!/usr/bin/env bash
# Layersentry V1.0 - Rocky Linux 9 safe recovery v2
#
# Recovery scope:
#   * exact CloudStack 4.22.1.1 RPMs are already installed
#   * the first installer stopped during the UI build
#   * no bridge/VLAN/storage changes are performed here
#
# UI dependency policy:
# Apache CloudStack 4.22.1.1 CI uses Node 16 + `npm install` + `npm run build`.
# Its package-lock is intentionally retained. `npm ci` is unsuitable because the
# upstream lock is not in strict sync with package.json, while deleting the lock
# resolves newer Vue compiler/tooling versions and can break the 4.22 UI build.

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
readonly LOG_FILE="/var/log/layersentry-rocky9-resume-v2-$(date +%Y%m%d-%H%M%S).log"

WORK_DIR=''
SOURCE_DIR=''
UI_ROOT=''
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
  printf 'ERROR: %s recovery v2 failed during %s (line %s, exit %s).\n' \
    "$PRODUCT" "$CURRENT_STAGE" "${BASH_LINENO[0]:-unknown}" "$rc" \
    | tee -a "$LOG_FILE" >&2
  printf 'ERROR: Review %s\n' "$LOG_FILE" | tee -a "$LOG_FILE" >&2
  exit "$rc"
}

cleanup() {
  if [[ -n "${WORK_DIR:-}" && -d "$WORK_DIR" ]]; then
    rm -rf -- "$WORK_DIR"
  fi
}
trap on_error ERR
trap cleanup EXIT

require_root() {
  [[ $EUID -eq 0 ]] || die 'Run this recovery as root.'
}

version_is_exact() {
  [[ "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" ||
     "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}."* ]]
}

validate_host() {
  stage 'validating exact interrupted installation'
  [[ -r /etc/os-release ]] || die '/etc/os-release is missing.'
  . /etc/os-release
  [[ "${ID:-}" == 'rocky' && "${VERSION_ID%%.*}" == '9' ]] \
    || die "Rocky Linux 9 required; detected ${PRETTY_NAME:-unknown}."
  [[ "$(uname -m)" == 'x86_64' ]] || die 'x86_64 required.'

  local management ui agent fqdn primary_ip
  management="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-management 2>/dev/null || true)"
  ui="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-ui 2>/dev/null || true)"
  agent="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-agent 2>/dev/null || true)"
  version_is_exact "$management" || die "cloudstack-management is ${management:-missing}; exact ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE} required."
  version_is_exact "$ui" || die "cloudstack-ui is ${ui:-missing}; exact ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE} required."
  version_is_exact "$agent" || die "cloudstack-agent is ${agent:-missing}; exact ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE} required."

  rpm -q mysql-server >/dev/null 2>&1 || die 'mysql-server package is missing.'
  java -version 2>&1 | head -1 | grep -Eq 'version "17([.]|\")' || die 'Java 17 is not active.'
  grep -Eq '(vmx|svm)' /proc/cpuinfo || die 'CPU virtualization extensions are not visible.'
  [[ -c /dev/kvm ]] || die '/dev/kvm is missing.'

  fqdn="$(hostname -f 2>/dev/null || true)"
  [[ "$fqdn" == "$EXPECTED_FQDN" ]] || die "Expected FQDN $EXPECTED_FQDN; detected ${fqdn:-none}."
  primary_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1);exit}}')"
  [[ "$primary_ip" == "$EXPECTED_IP" ]] || die "Expected management IP $EXPECTED_IP; detected ${primary_ip:-none}."

  info "Exact packages verified: management=$management ui=$ui agent=$agent."
  info "Host verified: $fqdn / $primary_ip; /dev/kvm present."
}

prepare_prerequisites() {
  stage 'preparing build and runtime prerequisites'
  dnf -y install ca-certificates curl git openssl python3 rsync tar gzip jq which \
    gcc-c++ make nodejs npm nfs-utils firewalld >>"$LOG_FILE" 2>&1

  local node_major
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$node_major" == '16' ]] \
    || die "CloudStack 4.22 UI recovery is pinned to Node 16; detected $(node --version 2>/dev/null || echo none)."
  info "Build runtime pinned: Node.js $(node --version), npm $(npm --version)."
}

build_ui() {
  stage 'building Layersentry UI using upstream CloudStack 4.22 npm method'
  WORK_DIR="$(mktemp -d /var/tmp/layersentry-rocky9-resume-v2.XXXXXX)"
  SOURCE_DIR="$WORK_DIR/source"

  git init -q "$SOURCE_DIR"
  git -C "$SOURCE_DIR" remote add origin "$UI_REPOSITORY"
  git -C "$SOURCE_DIR" config core.sparseCheckout true
  printf 'ui/\n' >"$SOURCE_DIR/.git/info/sparse-checkout"
  git -C "$SOURCE_DIR" -c protocol.version=2 fetch -q --depth 1 --filter=blob:none origin "$UI_COMMIT"
  git -C "$SOURCE_DIR" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" == "$UI_COMMIT" ]] \
    || die 'Pinned UI source provenance check failed.'
  [[ -f "$SOURCE_DIR/ui/package.json" && -f "$SOURCE_DIR/ui/package-lock.json" ]] \
    || die 'Pinned UI package metadata is incomplete.'

  pushd "$SOURCE_DIR/ui" >/dev/null
  export NODE_OPTIONS='--openssl-legacy-provider --max-old-space-size=4096'
  export npm_config_python=/usr/bin/python3
  export npm_config_cache='/root/.npm'

  rm -rf node_modules
  # Follow the Apache CloudStack 4.22.1.1 UI CI path: keep the upstream lock and
  # run npm install. npm reconciles manifest deltas while retaining compatible
  # lock-pinned Vue 3.2.x/compiler tooling. Never use npm ci here.
  npm install --no-audit --no-fund >>"$LOG_FILE" 2>&1
  {
    echo '===== RESOLVED UI TOOLCHAIN ====='
    npm ls --depth=0 vue @vue/compiler-sfc vue-loader @vue/cli-service webpack 2>&1 || true
    echo '===== END RESOLVED UI TOOLCHAIN ====='
  } >>"$LOG_FILE"
  npm run build >>"$LOG_FILE" 2>&1
  popd >/dev/null

  [[ -f "$SOURCE_DIR/ui/dist/index.html" ]] || die 'UI build did not produce dist/index.html.'
  [[ -f "$SOURCE_DIR/ui/dist/config.json" ]] || die 'UI build did not produce dist/config.json.'
  grep -Rqs --include='*.js' 'DBaaS' "$SOURCE_DIR/ui/dist" || die 'Compiled UI does not contain DBaaS.'
  grep -Rqs --include='*.js' 'APaaS' "$SOURCE_DIR/ui/dist" || die 'Compiled UI does not contain APaaS.'

  python3 - "$SOURCE_DIR/ui/dist/config.json" <<'PY'
import json, sys
p=sys.argv[1]
with open(p, encoding='utf-8') as f:
    c=json.load(f)
c['appTitle']='Layersentry'
c['loginTitle']='Layersentry'
c['loginFooter']='Secure cloud infrastructure management.'
c['footer']='Layersentry V1.0'
c['notifyLatestCSVersion']=False
c['apidocs']=False
if isinstance(c.get('userCard'), dict):
    c['userCard']['enabled']=False
with open(p,'w',encoding='utf-8') as f:
    json.dump(c,f,indent=2,ensure_ascii=False)
    f.write('\n')
PY
  python3 -m json.tool "$SOURCE_DIR/ui/dist/config.json" >/dev/null

  sha256sum "$SOURCE_DIR/ui/package.json" "$SOURCE_DIR/ui/package-lock.json" \
    "$SOURCE_DIR/ui/dist/index.html" >>"$LOG_FILE"
  info "UI build passed from pinned source $UI_COMMIT; DBaaS/APaaS compiled."
}

configure_mysql() {
  stage 'configuring MySQL'
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
  systemctl is-active --quiet mysqld || die 'mysqld failed to start.'
  mysql --protocol=socket -uroot -NBe 'SELECT 1' >/dev/null 2>&1 \
    || die 'Local MySQL root access is unavailable; recovery will not guess or expose a root password.'
  info 'MySQL is active and local root access is verified.'
}

mysql_query() {
  mysql --protocol=socket -uroot -NBe "$1"
}

database_complete() {
  local cloud usage
  cloud="$(mysql_query "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='cloud'" 2>/dev/null || echo 0)"
  usage="$(mysql_query "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='cloud_usage'" 2>/dev/null || echo 0)"
  [[ "$cloud" =~ ^[0-9]+$ && "$usage" =~ ^[0-9]+$ ]] || return 1
  ((cloud >= 50 && usage >= 1))
}

configure_database() {
  stage 'initializing CloudStack database idempotently'
  if mysql_query "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='cloud'" 2>/dev/null | grep -Fxq cloud; then
    database_complete || die "An existing cloud database is incomplete or unknown; refusing destructive recovery."
    info 'Existing CloudStack database is complete; preserving it.'
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

  cloudstack-setup-databases "cloud:${db_password}@localhost" --deploy-as=root -i "$EXPECTED_IP" \
    >>"$LOG_FILE" 2>&1
  unset db_password
  database_complete || die 'CloudStack database setup returned without the expected schemas/tables.'
  info "CloudStack database initialized; generated cloud-user credential is stored only in $SECRETS_FILE."
}

configure_management() {
  stage 'configuring CloudStack management server'
  cloudstack-setup-management >>"$LOG_FILE" 2>&1
  info 'cloudstack-setup-management completed.'
}

find_ui_root() {
  local index
  index="$(rpm -ql cloudstack-ui 2>/dev/null | awk '/\/index\.html$/ {print; exit}')"
  [[ -n "$index" && -f "$index" ]] || die 'Unable to locate the package-owned CloudStack UI root.'
  UI_ROOT="$(dirname "$index")"
}

deploy_ui() {
  stage 'backing up and deploying Layersentry UI'
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
  rsync -a --exclude='config.json' --chown=root:root --chmod=D755,F644 \
    "$SOURCE_DIR/ui/dist/" "$UI_ROOT/"
  install -D -m 0644 -o root -g root "$SOURCE_DIR/ui/dist/config.json" "$config_target"
  restorecon -RF "$UI_ROOT" "$config_target" >>"$LOG_FILE" 2>&1 || true
  info "Layersentry UI deployed; pre-deployment backup: $backup."
}

configure_firewall() {
  stage 'configuring firewall for SSH and Layersentry UI'
  if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --add-service=ssh >>"$LOG_FILE" 2>&1
    firewall-cmd --permanent --add-port=8080/tcp >>"$LOG_FILE" 2>&1
    firewall-cmd --reload >>"$LOG_FILE" 2>&1
  else
    firewall-offline-cmd --add-service=ssh >>"$LOG_FILE" 2>&1
    firewall-offline-cmd --add-port=8080/tcp >>"$LOG_FILE" 2>&1
    systemctl enable --now firewalld >>"$LOG_FILE" 2>&1
  fi
  firewall-cmd --query-service=ssh >/dev/null || die 'firewalld does not permit SSH.'
  firewall-cmd --query-port=8080/tcp >/dev/null || die 'firewalld does not permit TCP/8080.'
}

start_services() {
  stage 'starting and health-checking Layersentry'
  systemctl enable cloudstack-management >>"$LOG_FILE" 2>&1
  systemctl restart cloudstack-management >>"$LOG_FILE" 2>&1
  systemctl is-active --quiet cloudstack-management || die 'cloudstack-management is not active.'

  systemctl enable cloudstack-agent >>"$LOG_FILE" 2>&1 || true
  systemctl restart cloudstack-agent >>"$LOG_FILE" 2>&1 || true
  if ! systemctl is-active --quiet cloudstack-agent; then
    warn 'cloudstack-agent is not active yet; cloudbr0/KVM host networking is still intentionally pending.'
  fi

  local code='' attempt
  for attempt in $(seq 1 72); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 3 --max-time 8 \
      http://127.0.0.1:8080/client/ || true)"
    case "$code" in 200|302|401) break ;; esac
    sleep 5
  done
  case "$code" in
    200|302|401) ;;
    *) die "Layersentry UI health check failed; last HTTP status ${code:-none}." ;;
  esac
  info "Layersentry endpoint is healthy: HTTP $code."
}

final_evidence() {
  stage 'recording final installation evidence'
  {
    echo '===== PACKAGES ====='
    rpm -q cloudstack-management cloudstack-ui cloudstack-agent mysql-server
    echo '===== JAVA ====='
    java -version 2>&1 | head -3
    echo '===== SERVICES ====='
    systemctl is-active mysqld cloudstack-management || true
    systemctl is-active cloudstack-agent || true
    echo '===== KVM ====='
    ls -l /dev/kvm
    lsmod | grep kvm || true
    echo '===== LIBVIRT ====='
    virsh -c qemu:///system list --all || true
    echo '===== NETWORK ====='
    ip -4 -br addr
    ip route
    echo '===== HTTP ====='
    curl -sS -o /dev/null -w 'HTTP %{http_code}\n' --max-time 10 http://127.0.0.1:8080/client/ || true
  } | tee -a "$LOG_FILE"

  log '[100%] Layersentry V1.0 Rocky Linux 9 recovery v2 completed'
  log "Access URL: http://${EXPECTED_IP}:8080/client/"
  [[ -z "$SECRETS_FILE" ]] || log "Database credential file: $SECRETS_FILE (root-only)"
  log 'DBaaS/APaaS are compiled UI catalogs; provisioning remains disabled until backend integration is implemented.'
  log 'cloudbr0, guest/public networking and CloudStack storage remain intentionally unmodified.'
}

main() {
  require_root
  touch "$LOG_FILE"
  chmod 0600 "$LOG_FILE"
  log "$PRODUCT $PRODUCT_VERSION Rocky Linux 9 safe recovery v2"
  log "CloudStack internal release: $CLOUDSTACK_VERSION"
  log "Pinned Layersentry UI commit: $UI_COMMIT"
  log "Log: $LOG_FILE"

  validate_host
  prepare_prerequisites
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

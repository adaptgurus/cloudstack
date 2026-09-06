#!/usr/bin/env bash
# Layersentry V1.0 live branding repair for the validated Rocky Linux 9 host.
# Rebuilds the reviewed UI source, deploys it to the package-owned UI root,
# writes the customer-facing runtime config to the correct UI config path,
# restarts only the management service, and verifies the served application.

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly PRODUCT='Layersentry'
readonly PRODUCT_VERSION='V1.0'
readonly CLOUDSTACK_VERSION='4.22.1.1'
readonly CLOUDSTACK_RELEASE='1'
readonly UI_REPOSITORY='https://github.com/adaptgurus/cloudstack.git'
readonly UI_COMMIT='72b76a30f3dadf0dbe9e333ade073034c1afc514'
readonly EXPECTED_FQDN='layersentry.lab.example'
readonly EXPECTED_IP='10.10.10.14'
readonly UI_ROOT='/usr/share/cloudstack-ui'
readonly ETC_UI_CONFIG='/etc/cloudstack/ui/config.json'
readonly LOG_FILE="/var/log/layersentry-branding-repair-$(date +%Y%m%d-%H%M%S).log"

WORK_DIR=''
SOURCE_DIR=''
CURRENT_STAGE='initialization'

log() { printf '%s\n' "$*" | tee -a "$LOG_FILE"; }
info() { log "INFO: $*"; }
die() { log "ERROR: $*" >&2; exit 1; }
stage() { CURRENT_STAGE="$1"; log "==> $CURRENT_STAGE"; }

on_error() {
  local rc=$?
  set +e
  printf 'ERROR: %s branding repair failed during %s (line %s, exit %s).\n' \
    "$PRODUCT" "$CURRENT_STAGE" "${BASH_LINENO[0]:-unknown}" "$rc" | tee -a "$LOG_FILE" >&2
  exit "$rc"
}
cleanup() {
  [[ -z "${WORK_DIR:-}" || ! -d "$WORK_DIR" ]] || rm -rf -- "$WORK_DIR"
}
trap on_error ERR
trap cleanup EXIT

version_is_exact() {
  [[ "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" ||
     "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}."* ]]
}

validate_host() {
  stage 'validating target and current CloudStack installation'
  [[ $EUID -eq 0 ]] || die 'Run as root.'
  . /etc/os-release
  [[ "${ID:-}" == 'rocky' && "${VERSION_ID%%.*}" == '9' ]] || die 'This repair is scoped to Rocky Linux 9.'
  [[ "$(uname -m)" == 'x86_64' ]] || die 'x86_64 is required.'

  local management ui agent fqdn primary_ip
  management="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-management 2>/dev/null || true)"
  ui="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-ui 2>/dev/null || true)"
  agent="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' cloudstack-agent 2>/dev/null || true)"
  version_is_exact "$management" || die "Unexpected cloudstack-management version: ${management:-missing}."
  version_is_exact "$ui" || die "Unexpected cloudstack-ui version: ${ui:-missing}."
  version_is_exact "$agent" || die "Unexpected cloudstack-agent version: ${agent:-missing}."

  fqdn="$(hostname -f 2>/dev/null || true)"
  [[ "$fqdn" == "$EXPECTED_FQDN" ]] || die "Expected FQDN $EXPECTED_FQDN; got ${fqdn:-none}."
  primary_ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1);exit}}')"
  [[ "$primary_ip" == "$EXPECTED_IP" ]] || die "Expected IP $EXPECTED_IP; got ${primary_ip:-none}."

  [[ -d "$UI_ROOT" && -f "$UI_ROOT/index.html" ]] || die "Package-owned UI root $UI_ROOT is missing."
  systemctl is-active --quiet cloudstack-management || die 'cloudstack-management is not active.'
  local code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8080/client/ || true)"
  [[ "$code" == '200' ]] || die "Current UI endpoint is not healthy (HTTP ${code:-none})."
  info "Validated $EXPECTED_FQDN / $EXPECTED_IP with exact CloudStack $CLOUDSTACK_VERSION packages."
}

prepare_build_tools() {
  stage 'preparing proven CloudStack 4.22 UI build runtime'
  dnf -y install ca-certificates curl git python3 rsync tar gzip jq which gcc-c++ make nodejs npm >>"$LOG_FILE" 2>&1
  local node_major
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$node_major" == '16' ]] || die "CloudStack 4.22 UI build is pinned to Node.js 16; detected $(node --version 2>/dev/null || echo none)."
  info "Build runtime: Node.js $(node --version), npm $(npm --version)."
}

build_ui() {
  stage 'building reviewed Layersentry UI source'
  WORK_DIR="$(mktemp -d /var/tmp/layersentry-branding-repair.XXXXXX)"
  SOURCE_DIR="$WORK_DIR/source"
  git init -q "$SOURCE_DIR"
  git -C "$SOURCE_DIR" remote add origin "$UI_REPOSITORY"
  git -C "$SOURCE_DIR" config core.sparseCheckout true
  printf 'ui/\n' >"$SOURCE_DIR/.git/info/sparse-checkout"
  git -C "$SOURCE_DIR" -c protocol.version=2 fetch -q --depth 1 --filter=blob:none origin "$UI_COMMIT"
  git -C "$SOURCE_DIR" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" == "$UI_COMMIT" ]] || die 'UI source provenance verification failed.'

  pushd "$SOURCE_DIR/ui" >/dev/null
  export NODE_OPTIONS='--openssl-legacy-provider --max-old-space-size=4096'
  export npm_config_python=/usr/bin/python3
  rm -rf node_modules
  npm install --legacy-peer-deps --no-audit --no-fund >>"$LOG_FILE" 2>&1
  npm run build >>"$LOG_FILE" 2>&1
  popd >/dev/null

  [[ -f "$SOURCE_DIR/ui/dist/index.html" ]] || die 'Build did not produce dist/index.html.'
  [[ -f "$SOURCE_DIR/ui/dist/config.json" ]] || die 'Build did not produce dist/config.json.'
  grep -Rqs --include='*.js' 'DBaaS' "$SOURCE_DIR/ui/dist" || die 'Compiled UI does not contain DBaaS.'
  grep -Rqs --include='*.js' 'APaaS' "$SOURCE_DIR/ui/dist" || die 'Compiled UI does not contain APaaS.'
  grep -Rqs --include='*.js' 'Secure cloud infrastructure management' "$SOURCE_DIR/ui/dist" || die 'Compiled UI does not contain the Layersentry onboarding experience.'

  python3 - "$SOURCE_DIR/ui/dist/config.json" <<'PY'
import json,sys
p=sys.argv[1]
with open(p,encoding='utf-8') as f:
    c=json.load(f)
checks={
    'appTitle': c.get('appTitle') == 'Layersentry',
    'loginTitle': c.get('loginTitle') == 'Layersentry',
    'footer': c.get('footer') == 'Layersentry V1.0',
    'logo': c.get('logo') == 'assets/layersentry-logo.svg',
    'minilogo': c.get('minilogo') == 'assets/layersentry-icon.svg',
    'apidocs': c.get('apidocs') is False,
    'notifyLatestCSVersion': c.get('notifyLatestCSVersion') is False,
    'userCard': c.get('userCard',{}).get('enabled') is False,
}
print(checks)
assert all(checks.values())
PY
  info "Production UI build passed from $UI_COMMIT."
}

backup_runtime() {
  stage 'backing up current runtime UI'
  local stamp backup
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup="/var/backups/layersentry/${stamp}/cloudstack-ui-before-branding-repair.tar.gz"
  install -d -m 0700 "$(dirname "$backup")"
  tar --xattrs --acls -C "$UI_ROOT" -czf "$backup" .
  chmod 0600 "$backup"
  if [[ -e "$ETC_UI_CONFIG" || -L "$ETC_UI_CONFIG" ]]; then
    cp -aL "$ETC_UI_CONFIG" "${backup%.tar.gz}.etc-config.json"
    chmod 0600 "${backup%.tar.gz}.etc-config.json"
  fi
  info "Runtime backup created: $backup"
}

deploy_ui() {
  stage 'deploying Layersentry UI and correct runtime config'
  local runtime_config resolved
  runtime_config="$UI_ROOT/config.json"

  systemctl stop cloudstack-management >>"$LOG_FILE" 2>&1
  rsync -a --delete --exclude='config.json' --chown=root:root --chmod=D755,F644 \
    "$SOURCE_DIR/ui/dist/" "$UI_ROOT/"

  install -d -m 0755 /etc/cloudstack/ui
  install -m 0644 -o root -g root "$SOURCE_DIR/ui/dist/config.json" "$ETC_UI_CONFIG"

  if [[ -L "$runtime_config" ]]; then
    resolved="$(readlink -f "$runtime_config")"
    [[ -n "$resolved" ]] || die 'Unable to resolve runtime config symlink.'
    install -m 0644 -o root -g root "$SOURCE_DIR/ui/dist/config.json" "$resolved"
  else
    install -m 0644 -o root -g root "$SOURCE_DIR/ui/dist/config.json" "$runtime_config"
  fi

  install -D -m 0644 -o root -g root "$SOURCE_DIR/ui/dist/assets/layersentry-logo.svg" "$UI_ROOT/assets/layersentry-logo.svg"
  install -D -m 0644 -o root -g root "$SOURCE_DIR/ui/dist/assets/layersentry-icon.svg" "$UI_ROOT/assets/layersentry-icon.svg"
  restorecon -RF /etc/cloudstack/ui "$UI_ROOT" >>"$LOG_FILE" 2>&1 || true

  systemctl start cloudstack-management >>"$LOG_FILE" 2>&1
  info 'Layersentry UI files deployed and management service restarted.'
}

verify_runtime() {
  stage 'verifying served Layersentry application'
  local code='' attempt
  for attempt in $(seq 1 60); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 3 --max-time 8 http://127.0.0.1:8080/client/ || true)"
    [[ "$code" == '200' ]] && break
    sleep 5
  done
  [[ "$code" == '200' ]] || die "UI health check failed; last HTTP code ${code:-none}."

  curl -fsS --max-time 15 http://127.0.0.1:8080/client/config.json -o "$WORK_DIR/runtime-config.json"
  python3 - "$WORK_DIR/runtime-config.json" <<'PY'
import json,sys
with open(sys.argv[1],encoding='utf-8') as f:
    c=json.load(f)
checks={
    'appTitle': c.get('appTitle') == 'Layersentry',
    'loginTitle': c.get('loginTitle') == 'Layersentry',
    'footer': c.get('footer') == 'Layersentry V1.0',
    'logo': c.get('logo') == 'assets/layersentry-logo.svg',
    'minilogo': c.get('minilogo') == 'assets/layersentry-icon.svg',
    'apidocs': c.get('apidocs') is False,
    'notifyLatestCSVersion': c.get('notifyLatestCSVersion') is False,
    'userCard': c.get('userCard',{}).get('enabled') is False,
}
print('RUNTIME_CONFIG_CHECKS=' + json.dumps(checks,sort_keys=True))
assert all(checks.values())
PY

  for asset in layersentry-logo.svg layersentry-icon.svg; do
    local acode
    acode="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "http://127.0.0.1:8080/client/assets/$asset" || true)"
    [[ "$acode" == '200' ]] || die "Runtime asset $asset failed HTTP check: $acode."
  done

  grep -Rqs --include='*.js' 'DBaaS' "$UI_ROOT" || die 'Deployed runtime does not contain DBaaS.'
  grep -Rqs --include='*.js' 'APaaS' "$UI_ROOT" || die 'Deployed runtime does not contain APaaS.'
  grep -Rqs --include='*.js' 'Secure cloud infrastructure management' "$UI_ROOT" || die 'Deployed runtime does not contain Layersentry onboarding text.'

  printf '%s\n' '===== SERVED CONFIG =====' | tee -a "$LOG_FILE"
  cat "$WORK_DIR/runtime-config.json" | tee -a "$LOG_FILE"
  printf '%s\n' '===== RESPONSE HEADERS =====' | tee -a "$LOG_FILE"
  curl -sSI --max-time 15 http://127.0.0.1:8080/client/ | tee -a "$LOG_FILE" || true
  curl -sSI --max-time 15 http://127.0.0.1:8080/client/config.json | tee -a "$LOG_FILE" || true

  log '[100%] Layersentry V1.0 live branding repair completed'
  log "Access URL: http://${EXPECTED_IP}:8080/client/"
  log "UI source: ${UI_COMMIT}"
  log 'DBaaS=PASS APaaS=PASS ONBOARDING=PASS RUNTIME_CONFIG=PASS HTTP=200'
}

main() {
  log 'Layersentry V1.0 Rocky Linux 9 live branding repair'
  log "Log: $LOG_FILE"
  validate_host
  prepare_build_tools
  build_ui
  backup_runtime
  deploy_ui
  verify_runtime
}

main "$@"

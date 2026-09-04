#!/usr/bin/env bash
# Layersentry V1.0 served-UI branding repair for Rocky Linux 9.
#
# CloudStack 4.22 management serves an exploded Jetty webapp from the management
# runtime, so replacing only the cloudstack-ui RPM payload is not sufficient on an
# already-started management node. This repair rebuilds the reviewed Layersentry
# UI, overlays only static UI content into the management webapp, preserves
# WEB-INF/META-INF, writes the runtime config, restarts management, and verifies
# the actually served application.
#
# It never creates/modifies zones, pods, clusters, hosts, cloudbr0, VLANs,
# guest/public networks, primary/secondary storage, or CloudStack database data.

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly PRODUCT='Layersentry'
readonly PRODUCT_VERSION='V1.0'
readonly CLOUDSTACK_VERSION='4.22.1.1'
readonly CLOUDSTACK_RELEASE='1'
readonly UI_REPOSITORY='https://github.com/adaptgurus/cloudstack.git'
readonly UI_COMMIT='72b76a30f3dadf0dbe9e333ade073034c1afc514'
readonly SERVED_UI='/usr/share/cloudstack-management/webapp'
readonly SERVED_CONFIG='/etc/cloudstack/management/config.json'
readonly HTTP_URL='http://127.0.0.1:8080/client/'
readonly CONFIG_URL='http://127.0.0.1:8080/client/config.json'

VERIFY_ONLY=0
WORK_DIR=''
SOURCE_DIR=''
LOG_FILE="/var/log/layersentry-served-ui-branding-$(date +%Y%m%d-%H%M%S).log"
CURRENT_STAGE='initialization'

log(){ printf '%s\n' "$*" | tee -a "$LOG_FILE"; }
info(){ log "INFO: $*"; }
die(){ log "ERROR: $*" >&2; exit 1; }
stage(){ CURRENT_STAGE="$1"; log "==> $CURRENT_STAGE"; }

on_error(){
  local rc=$?
  set +e
  printf 'ERROR: %s served-UI branding failed during %s (line %s, exit %s).\n' \
    "$PRODUCT" "$CURRENT_STAGE" "${BASH_LINENO[0]:-unknown}" "$rc" \
    | tee -a "$LOG_FILE" >&2
  exit "$rc"
}
cleanup(){
  [[ -z "${WORK_DIR:-}" || ! -d "$WORK_DIR" ]] || rm -rf -- "$WORK_DIR"
}
trap on_error ERR
trap cleanup EXIT

usage(){
  cat <<'USAGE'
Layersentry V1.0 Rocky Linux 9 served-UI branding repair

Usage:
  sudo ./install-layersentry-rocky9-served-ui-repair.sh [--verify-only]

Options:
  --verify-only   Read-only verification of the currently served UI. No rebuild,
                  file replacement, service restart, database or infrastructure change.
  -h, --help      Show this help.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

version_is_exact(){
  [[ "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" ||
     "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}."* ]]
}

validate_target(){
  stage 'validating Rocky Linux 9 and exact CloudStack package layout'
  [[ $EUID -eq 0 ]] || die 'Run as root.'
  . /etc/os-release
  [[ "${ID:-}" == 'rocky' && "${VERSION_ID%%.*}" == '9' ]] \
    || die "Rocky Linux 9 is required; detected ${PRETTY_NAME:-unknown}."
  [[ "$(uname -m)" == 'x86_64' ]] || die 'x86_64 is required.'

  local pkg value
  for pkg in cloudstack-management cloudstack-ui; do
    value="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' "$pkg" 2>/dev/null || true)"
    version_is_exact "$value" || die "Expected $pkg ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}; found ${value:-missing}."
  done
  [[ -d "$SERVED_UI" && -d "$SERVED_UI/WEB-INF" ]] \
    || die "CloudStack management webapp is missing at $SERVED_UI."
  systemctl is-active --quiet cloudstack-management \
    || die 'cloudstack-management must be active before branding repair.'
  info "Target validated: $(hostname -f 2>/dev/null || hostname), CloudStack $CLOUDSTACK_VERSION."
}

prepare_build_runtime(){
  stage 'preparing CloudStack 4.22 UI build runtime'
  dnf -y install dnf-plugins-core >>"$LOG_FILE" 2>&1
  dnf -y module reset nodejs >>"$LOG_FILE" 2>&1 || true
  dnf -y module enable nodejs:16 >>"$LOG_FILE" 2>&1 \
    || die 'Unable to enable Rocky Linux 9 Node.js 16 module.'
  dnf -y install ca-certificates curl git python3 rsync tar gzip jq which \
    gcc-c++ make nodejs npm >>"$LOG_FILE" 2>&1
  local node_major
  node_major="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$node_major" == '16' ]] \
    || die "CloudStack 4.22 UI build requires Node.js 16; detected $(node --version 2>/dev/null || echo none)."
  info "Build runtime: Node.js $(node --version), npm $(npm --version)."
}

build_ui(){
  stage 'building reviewed Layersentry UI'
  WORK_DIR="$(mktemp -d /var/tmp/layersentry-served-ui.XXXXXX)"
  SOURCE_DIR="$WORK_DIR/source"
  git init -q "$SOURCE_DIR"
  git -C "$SOURCE_DIR" remote add origin "$UI_REPOSITORY"
  git -C "$SOURCE_DIR" config core.sparseCheckout true
  printf 'ui/\n' >"$SOURCE_DIR/.git/info/sparse-checkout"
  git -C "$SOURCE_DIR" -c protocol.version=2 fetch -q --depth 1 --filter=blob:none origin "$UI_COMMIT"
  git -C "$SOURCE_DIR" checkout -q --detach FETCH_HEAD
  [[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" == "$UI_COMMIT" ]] \
    || die 'Layersentry UI source provenance verification failed.'

  pushd "$SOURCE_DIR/ui" >/dev/null
  export NODE_OPTIONS='--openssl-legacy-provider --max-old-space-size=4096'
  export npm_config_python=/usr/bin/python3
  rm -rf node_modules
  # CloudStack 4.22 upstream UI CI uses npm install with Node 16. Keep the
  # historical package-lock; do not switch to npm ci or delete the lockfile.
  npm install --no-audit --no-fund >>"$LOG_FILE" 2>&1
  npm run build >>"$LOG_FILE" 2>&1
  popd >/dev/null

  [[ -f "$SOURCE_DIR/ui/dist/index.html" && -f "$SOURCE_DIR/ui/dist/config.json" ]] \
    || die 'Layersentry production build did not produce index.html/config.json.'
  grep -Rqs --include='*.js' 'DBaaS' "$SOURCE_DIR/ui/dist" || die 'DBaaS is absent from the compiled UI.'
  grep -Rqs --include='*.js' 'APaaS' "$SOURCE_DIR/ui/dist" || die 'APaaS is absent from the compiled UI.'
  grep -Rqs --include='*.js' 'Secure cloud infrastructure management' "$SOURCE_DIR/ui/dist" \
    || die 'Layersentry onboarding is absent from the compiled UI.'
  validate_config_file "$SOURCE_DIR/ui/dist/config.json" 'BUILD_CONFIG_CHECKS'
  info "Production UI build passed from immutable source $UI_COMMIT."
}

validate_config_file(){
  local file="$1" label="$2"
  python3 - "$file" "$label" <<'PY'
import json,sys
p,label=sys.argv[1],sys.argv[2]
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
print(label+'='+json.dumps(checks,sort_keys=True))
assert all(checks.values())
PY
}

backup_runtime(){
  stage 'backing up the served management webapp'
  local stamp backup_dir
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup_dir="/var/backups/layersentry/${stamp}/served-ui-before-branding"
  install -d -m 0700 "$backup_dir"
  tar --xattrs --acls -C /usr/share/cloudstack-management -czf "$backup_dir/webapp-before.tar.gz" webapp
  chmod 0600 "$backup_dir/webapp-before.tar.gz"
  if [[ -e "$SERVED_CONFIG" || -L "$SERVED_CONFIG" ]]; then
    cp -aL "$SERVED_CONFIG" "$backup_dir/config.json.before"
    chmod 0600 "$backup_dir/config.json.before"
  fi
  info "Runtime backup created: $backup_dir"
}

deploy_runtime(){
  stage 'deploying Layersentry into the served management webapp'
  # Overlay only static UI content. Backend WEB-INF/META-INF are explicitly
  # excluded and are never deleted or replaced by this branding operation.
  systemctl stop cloudstack-management >>"$LOG_FILE" 2>&1
  rsync -a --delete \
    --exclude='config.json' --exclude='WEB-INF' --exclude='META-INF' \
    --chown=root:root --chmod=D755,F644 \
    "$SOURCE_DIR/ui/dist/" "$SERVED_UI/"
  install -D -m 0644 -o root -g root "$SOURCE_DIR/ui/dist/config.json" "$SERVED_CONFIG"
  rm -f "$SERVED_UI/config.json"
  ln -s "$SERVED_CONFIG" "$SERVED_UI/config.json"
  restorecon -RF "$SERVED_UI" "$SERVED_CONFIG" >>"$LOG_FILE" 2>&1 || true
  systemctl start cloudstack-management >>"$LOG_FILE" 2>&1
}

wait_for_http(){
  stage 'waiting for management HTTP readiness'
  local code='' attempt
  for attempt in $(seq 1 90); do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 3 --max-time 6 "$HTTP_URL" || true)"
    [[ "$code" == '200' ]] && { info 'Management endpoint returned HTTP 200.'; return 0; }
    sleep 5
  done
  die "Management endpoint did not return HTTP 200; last code ${code:-none}."
}

verify_runtime(){
  stage 'verifying the actually served Layersentry runtime'
  local tmp asset code
  tmp="$(mktemp /tmp/layersentry-runtime-config.XXXXXX.json)"
  curl -fsS --max-time 15 "$CONFIG_URL" -o "$tmp"
  validate_config_file "$tmp" 'RUNTIME_CONFIG_CHECKS'
  rm -f "$tmp"

  for asset in layersentry-logo.svg layersentry-icon.svg; do
    code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "${HTTP_URL}assets/${asset}")"
    [[ "$code" == '200' ]] || die "Served asset $asset returned HTTP $code."
  done

  grep -Rqs --include='*.js' 'DBaaS' "$SERVED_UI" || die 'DBaaS is absent from the served management webapp.'
  grep -Rqs --include='*.js' 'APaaS' "$SERVED_UI" || die 'APaaS is absent from the served management webapp.'
  grep -Rqs --include='*.js' 'Secure cloud infrastructure management' "$SERVED_UI" \
    || die 'Layersentry onboarding is absent from the served management webapp.'
  [[ "$(readlink -f "$SERVED_UI/config.json")" == "$SERVED_CONFIG" ]] \
    || die 'Served config symlink does not resolve to the management runtime config.'
  systemctl is-active --quiet cloudstack-management || die 'cloudstack-management is not active.'

  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "$HTTP_URL")"
  [[ "$code" == '200' ]] || die "Final UI endpoint returned HTTP $code."

  log "HTTP=$code"
  log "SERVED_CONFIG=$(readlink -f "$SERVED_UI/config.json")"
  log 'DBaaS=PASS APaaS=PASS ONBOARDING=PASS LOGO_ASSETS=PASS RUNTIME_CONFIG=PASS'
  log '[100%] Layersentry V1.0 served-UI branding verified'
}

main(){
  log 'Layersentry V1.0 Rocky Linux 9 served-UI branding repair'
  log "Log: $LOG_FILE"
  validate_target
  if ((VERIFY_ONLY)); then
    wait_for_http
    verify_runtime
    return 0
  fi
  prepare_build_runtime
  build_ui
  backup_runtime
  deploy_runtime
  wait_for_http
  verify_runtime
}

main "$@"

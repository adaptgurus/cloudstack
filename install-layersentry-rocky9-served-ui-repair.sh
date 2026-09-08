#!/usr/bin/env bash
# Layersentry V1.0 served-UI branding repair for Rocky Linux 9.
#
# CloudStack 4.22 management serves its UI from the management webapp. Replacing
# only the cloudstack-ui RPM payload can therefore leave an already-running
# management node serving stale upstream assets. This script repairs the
# actually served webapp while preserving backend WEB-INF/META-INF.
#
# It never creates/modifies zones, pods, clusters, hosts, cloudbr0, VLANs,
# guest/public networks, storage, or CloudStack database data.

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly PRODUCT='Layersentry'
readonly CLOUDSTACK_VERSION='4.22.1.1'
readonly CLOUDSTACK_RELEASE='1'
readonly UI_REPOSITORY='https://github.com/adaptgurus/cloudstack.git'
readonly UI_COMMIT='6ce76d6c241629086ffcad794093dbdd5f2dd5ba'
readonly STAGED_UI='/usr/share/cloudstack-ui'
readonly SERVED_UI='/usr/share/cloudstack-management/webapp'
readonly SERVED_CONFIG='/etc/cloudstack/management/config.json'
readonly HTTP_URL='http://127.0.0.1:8080/client/'
readonly CONFIG_URL='http://127.0.0.1:8080/client/config.json'

VERIFY_ONLY=0
FROM_STAGED=0
WORK_DIR=''
SOURCE_DIR=''
DEPLOY_SOURCE=''
LOG_FILE="/var/log/layersentry-served-ui-branding-$(date +%Y%m%d-%H%M%S).log"
CURRENT_STAGE='initialization'

log(){ printf '%s\n' "$*" | tee -a "$LOG_FILE"; }
info(){ log "INFO: $*"; }
die(){ log "ERROR: $*" >&2; exit 1; }
stage(){ CURRENT_STAGE="$1"; log "==> $CURRENT_STAGE"; }
on_error(){ local rc=$?; set +e; log "ERROR: $PRODUCT served-UI branding failed during $CURRENT_STAGE at line ${BASH_LINENO[0]:-unknown} (exit $rc)."; exit "$rc"; }
cleanup(){ [[ -z "${WORK_DIR:-}" || ! -d "$WORK_DIR" ]] || rm -rf -- "$WORK_DIR"; }
trap on_error ERR
trap cleanup EXIT

usage(){
  cat <<'USAGE'
Layersentry V1.0 Rocky Linux 9 served-UI branding repair

Usage:
  sudo ./install-layersentry-rocky9-served-ui-repair.sh [option]

Options:
  --from-staged   Deploy the already-built /usr/share/cloudstack-ui payload after
                  validating Layersentry config, V1 placeholder removal,
                  customer terminology and onboarding. This avoids a second npm
                  build when called by the main installer.
  --verify-only   Read-only verification of the currently served Layersentry UI.
  -h, --help      Show this help.
USAGE
}

for arg in "$@"; do
  case "$arg" in
    --from-staged) FROM_STAGED=1 ;;
    --verify-only) VERIFY_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "ERROR: unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done
((FROM_STAGED + VERIFY_ONLY <= 1)) || { echo 'ERROR: --from-staged and --verify-only are mutually exclusive.' >&2; exit 2; }

version_is_exact(){ [[ "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}" || "$1" == "${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}."* ]]; }

validate_config_file(){
  local file="$1" label="$2"
  python3 - "$file" "$label" <<'PY'
import json,sys
p,label=sys.argv[1],sys.argv[2]
with open(p,encoding='utf-8') as f: c=json.load(f)
checks={
 'appTitle':c.get('appTitle')=='Layersentry',
 'brandLocked':c.get('brandLocked') is True,
 'loginTitle':c.get('loginTitle')=='Layersentry',
 'footer':c.get('footer')=='Layersentry V1.0',
 'logo':c.get('logo')=='assets/layersentry-logo.svg',
 'minilogo':c.get('minilogo')=='assets/layersentry-icon.svg',
 'apidocs':c.get('apidocs') is False,
 'notifyLatestCSVersion':c.get('notifyLatestCSVersion') is False,
 'userCard':c.get('userCard',{}).get('enabled') is False,
}
print(label+'='+json.dumps(checks,sort_keys=True))
assert all(checks.values())
PY
}

fail_if_placeholder_present(){
  local root="$1" label="$2" term="$3" matches
  matches="$(grep -RIl --include='*.js' -- "$term" "$root" 2>/dev/null || true)"
  if [[ -n "$matches" ]]; then
    log "ERROR: obsolete $term placeholder marker found in $label JavaScript:"
    log "$matches"
    die "Obsolete $term placeholder is present in $label."
  fi
}

validate_ui_tree(){
  local root="$1" label="$2"
  [[ -f "$root/index.html" && -f "$root/config.json" ]] || die "$label is missing index.html/config.json at $root."
  validate_config_file "$root/config.json" "${label}_CONFIG_CHECKS"
  fail_if_placeholder_present "$root" "$label" 'DBaaS'
  fail_if_placeholder_present "$root" "$label" 'APaaS'
  grep -Rqs --include='*.js' 'Secure cloud infrastructure management' "$root" || die "Layersentry onboarding is absent from $label."
  grep -Rqs --include='*.js' 'Infrastructure group name' "$root" || die "Customer-friendly infrastructure terminology is absent from $label."
  grep -Rqs --include='*.js' 'Datacenter site' "$root" || die "Customer-friendly site terminology is absent from $label."
  grep -Rqs --include='*.js' 'Management network gateway' "$root" || die "Customer-friendly management-network terminology is absent from $label."
  [[ -f "$root/assets/layersentry-logo.svg" && -f "$root/assets/layersentry-icon.svg" ]] || die "Layersentry logo assets are absent from $label."
}

validate_target(){
  stage 'validating Rocky Linux 9 and exact CloudStack package layout'
  [[ $EUID -eq 0 ]] || die 'Run as root.'
  . /etc/os-release
  [[ "${ID:-}" == 'rocky' && "${VERSION_ID%%.*}" == '9' ]] || die "Rocky Linux 9 is required; detected ${PRETTY_NAME:-unknown}."
  [[ "$(uname -m)" == 'x86_64' ]] || die 'x86_64 is required.'
  local pkg value
  for pkg in cloudstack-management cloudstack-ui; do
    value="$(rpm -q --qf '%{VERSION}-%{RELEASE}\n' "$pkg" 2>/dev/null || true)"
    version_is_exact "$value" || die "Expected $pkg ${CLOUDSTACK_VERSION}-${CLOUDSTACK_RELEASE}; found ${value:-missing}."
  done
  [[ -d "$SERVED_UI" && -d "$SERVED_UI/WEB-INF" ]] || die "Management webapp is missing at $SERVED_UI."
  systemctl is-active --quiet cloudstack-management || die 'cloudstack-management must be active before branding repair.'
  info "Target validated: $(hostname -f 2>/dev/null || hostname), CloudStack $CLOUDSTACK_VERSION."
}

prepare_build_runtime(){
  stage 'preparing CloudStack 4.22 UI build runtime'
  dnf -y install dnf-plugins-core ca-certificates curl git python3 rsync tar gzip jq which gcc-c++ make >>"$LOG_FILE" 2>&1

  local node_major=''
  if command -v node >/dev/null 2>&1; then
    node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
  fi

  if [[ "$node_major" == '16' ]] && command -v npm >/dev/null 2>&1; then
    info "Reusing existing UI build runtime: Node.js $(node --version), npm $(npm --version)."
    return 0
  fi

  dnf -y module reset nodejs >>"$LOG_FILE" 2>&1 || true
  if ! dnf -y module enable nodejs:16 >>"$LOG_FILE" 2>&1; then
    die "Node.js 16 is not installed and the Rocky Linux 9 nodejs:16 module is unavailable; detected $(node --version 2>/dev/null || echo none)."
  fi
  dnf -y install nodejs npm >>"$LOG_FILE" 2>&1
  [[ "$(node -p 'process.versions.node.split(".")[0]')" == '16' ]] || die "CloudStack 4.22 UI build requires Node.js 16; detected $(node --version 2>/dev/null || echo none)."
  command -v npm >/dev/null 2>&1 || die 'npm is required for the Layersentry UI build.'
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
  [[ "$(git -C "$SOURCE_DIR" rev-parse HEAD)" == "$UI_COMMIT" ]] || die 'Layersentry UI source provenance verification failed.'
  pushd "$SOURCE_DIR/ui" >/dev/null
  export NODE_OPTIONS='--openssl-legacy-provider --max-old-space-size=4096'
  export npm_config_python=/usr/bin/python3
  rm -rf node_modules
  npm install --no-audit --no-fund >>"$LOG_FILE" 2>&1
  npm run build >>"$LOG_FILE" 2>&1
  popd >/dev/null
  DEPLOY_SOURCE="$SOURCE_DIR/ui/dist"
  validate_ui_tree "$DEPLOY_SOURCE" 'BUILD'
  info "Production UI build passed from immutable source $UI_COMMIT."
}

use_staged_ui(){
  stage 'validating existing staged Layersentry build'
  validate_ui_tree "$STAGED_UI" 'STAGED'
  DEPLOY_SOURCE="$STAGED_UI"
  info 'Validated staged Layersentry UI; second npm build skipped.'
}

backup_runtime(){
  stage 'backing up the served management webapp'
  local stamp backup_dir
  stamp="$(date +%Y%m%d-%H%M%S)"
  backup_dir="/var/backups/layersentry/${stamp}/served-ui-before-branding"
  install -d -m 0700 "$backup_dir"
  tar --xattrs --acls -C /usr/share/cloudstack-management -czf "$backup_dir/webapp-before.tar.gz" webapp
  chmod 0600 "$backup_dir/webapp-before.tar.gz"
  if [[ -e "$SERVED_CONFIG" || -L "$SERVED_CONFIG" ]]; then cp -aL "$SERVED_CONFIG" "$backup_dir/config.json.before"; chmod 0600 "$backup_dir/config.json.before"; fi
  info "Runtime backup created: $backup_dir"
}

deploy_runtime(){
  stage 'deploying Layersentry into the served management webapp'
  [[ -n "$DEPLOY_SOURCE" ]] || die 'No validated deployment source selected.'
  systemctl stop cloudstack-management >>"$LOG_FILE" 2>&1
  rsync -a --delete --exclude='config.json' --exclude='WEB-INF' --exclude='META-INF' --chown=root:root --chmod=D755,F644 "$DEPLOY_SOURCE/" "$SERVED_UI/"
  install -D -m 0644 -o root -g root "$DEPLOY_SOURCE/config.json" "$SERVED_CONFIG"
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
  fail_if_placeholder_present "$SERVED_UI" 'served webapp' 'DBaaS'
  fail_if_placeholder_present "$SERVED_UI" 'served webapp' 'APaaS'
  grep -Rqs --include='*.js' 'Secure cloud infrastructure management' "$SERVED_UI" || die 'Layersentry onboarding is absent from the served webapp.'
  grep -Rqs --include='*.js' 'Infrastructure group name' "$SERVED_UI" || die 'Customer-friendly infrastructure terminology is absent from the served webapp.'
  grep -Rqs --include='*.js' 'Datacenter site' "$SERVED_UI" || die 'Customer-friendly site terminology is absent from the served webapp.'
  grep -Rqs --include='*.js' 'Management network gateway' "$SERVED_UI" || die 'Customer-friendly management-network terminology is absent from the served webapp.'
  [[ "$(readlink -f "$SERVED_UI/config.json")" == "$SERVED_CONFIG" ]] || die 'Served config symlink target is wrong.'
  systemctl is-active --quiet cloudstack-management || die 'cloudstack-management is not active.'
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 "$HTTP_URL")"
  [[ "$code" == '200' ]] || die "Final UI endpoint returned HTTP $code."
  log "HTTP=$code"
  log "SERVED_CONFIG=$(readlink -f "$SERVED_UI/config.json")"
  log 'V1_PLACEHOLDERS=ABSENT ONBOARDING=PASS LOGO_ASSETS=PASS RUNTIME_CONFIG=PASS TERMINOLOGY=PASS'
  log '[100%] Layersentry V1.0 served-UI branding verified'
}

main(){
  log 'Layersentry V1.0 Rocky Linux 9 served-UI branding repair'
  log "Log: $LOG_FILE"
  validate_target
  if ((VERIFY_ONLY)); then wait_for_http; verify_runtime; return 0; fi
  if ((FROM_STAGED)); then use_staged_ui; else prepare_build_runtime; build_ui; fi
  backup_runtime
  deploy_runtime
  wait_for_http
  verify_runtime
}

main "$@"

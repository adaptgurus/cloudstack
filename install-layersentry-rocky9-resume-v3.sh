#!/usr/bin/env bash
# Layersentry V1.0 Rocky Linux 9 recovery v3.
#
# Recovers an interrupted exact CloudStack 4.22.1.1 installation using the proven
# v2 path, pins the current reviewed Layersentry UI source, fixes the historical
# pipefail UI-root lookup, then deploys that validated staged build into the
# management webapp that is actually served on TCP/8080.

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly V2_COMMIT='6617de6ee417c8970d9085431a8aa62de9698b2d'
readonly V2_URL="https://raw.githubusercontent.com/adaptgurus/cloudstack/${V2_COMMIT}/install-layersentry-rocky9-resume-v2.sh"
readonly UI_COMMIT='9ad724eb76843d40d6a883c0a0ab47a75ceed449'
readonly SERVED_BRANDING_COMMIT='49dbbeafe6e02c0797dac8d675e89ec440e44437'
readonly SERVED_BRANDING_URL="https://raw.githubusercontent.com/adaptgurus/cloudstack/${SERVED_BRANDING_COMMIT}/install-layersentry-rocky9-served-ui-repair.sh"
readonly PATCHED='/root/install-layersentry-rocky9-resume-v3-runtime.sh'
readonly BRANDING='/root/install-layersentry-rocky9-served-ui-repair.sh'

[[ $EUID -eq 0 ]] || { echo 'ERROR: run as root.' >&2; exit 1; }

curl -fsSL --retry 4 --retry-all-errors --connect-timeout 15 --max-time 120 "$V2_URL" -o "$PATCHED"
chmod 0700 "$PATCHED"

python3 - "$PATCHED" "$UI_COMMIT" <<'PY'
from pathlib import Path
import sys

p=Path(sys.argv[1])
ui_commit=sys.argv[2]
s=p.read_text(encoding='utf-8')

old_root='''  local index\n  index="$(rpm -ql cloudstack-ui 2>/dev/null | awk '/\\/index\\.html$/ {print; exit}')"\n'''
new_root='''  local index ui_files\n  ui_files="$(rpm -ql cloudstack-ui 2>/dev/null)"\n  index="$(awk '/\\/index\\.html$/ {print; exit}' <<<"$ui_files")"\n'''
if s.count(old_root) != 1:
    raise SystemExit(f'ERROR: expected one v2 UI-root pipeline; found {s.count(old_root)}.')
s=s.replace(old_root,new_root,1)

old_commit="readonly UI_COMMIT='6d364150095ba5cfd433746dca1f13d38ca1951f'"
new_commit=f"readonly UI_COMMIT='{ui_commit}'"
if s.count(old_commit) != 1:
    raise SystemExit(f'ERROR: expected one v2 UI source pin; found {s.count(old_commit)}.')
s=s.replace(old_commit,new_commit,1)

p.write_text(s,encoding='utf-8')
PY

bash -n "$PATCHED"
grep -Fq 'ui_files="$(rpm -ql cloudstack-ui 2>/dev/null)"' "$PATCHED" || { echo 'ERROR: pipefail-safe UI-root patch verification failed.' >&2; exit 1; }
grep -Fq "readonly UI_COMMIT='$UI_COMMIT'" "$PATCHED" || { echo 'ERROR: Layersentry UI source pin verification failed.' >&2; exit 1; }

"$PATCHED"

# The package payload is now current, but CloudStack management may still have an
# exploded Jetty webapp. Deploy the validated staged UI there without rebuilding.
curl -fsSL --retry 4 --retry-all-errors --connect-timeout 15 --max-time 120 "$SERVED_BRANDING_URL" -o "$BRANDING"
chmod 0700 "$BRANDING"
bash -n "$BRANDING"
"$BRANDING" --from-staged

echo '[100%] Layersentry V1.0 Rocky Linux 9 recovery and served-UI deployment completed'

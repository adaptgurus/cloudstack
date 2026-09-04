#!/usr/bin/env bash
# Layersentry V1.0 Rocky Linux 9 recovery v3.
#
# v2 proved the upstream-aligned Node 16 + npm install + npm build path and
# successfully initialized MySQL/CloudStack, but stopped while locating the
# package-owned UI root because `rpm -ql | awk ... exit` runs under pipefail:
# awk exits after the first index.html and rpm receives SIGPIPE (141).
#
# This immutable wrapper fetches the proven v2 recovery from its exact commit,
# applies only the pipefail-safe UI-root discovery correction, syntax-checks the
# result, and executes it. It does not alter network bridges, VLANs, storage or
# Hyper-V VM definitions.

set -Eeuo pipefail
IFS=$'\n\t'
umask 077

readonly V2_COMMIT='6617de6ee417c8970d9085431a8aa62de9698b2d'
readonly V2_URL="https://raw.githubusercontent.com/adaptgurus/cloudstack/${V2_COMMIT}/install-layersentry-rocky9-resume-v2.sh"
readonly PATCHED='/root/install-layersentry-rocky9-resume-v3-runtime.sh'

[[ $EUID -eq 0 ]] || { echo 'ERROR: run as root.' >&2; exit 1; }

curl -fsSL --retry 4 --retry-all-errors --connect-timeout 15 --max-time 120 \
  "$V2_URL" -o "$PATCHED"
chmod 0700 "$PATCHED"

python3 - "$PATCHED" <<'PY'
from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text(encoding='utf-8')
old = '''  local index\n  index="$(rpm -ql cloudstack-ui 2>/dev/null | awk '/\\/index\\.html$/ {print; exit}')"\n'''
new = '''  local index ui_files\n  ui_files="$(rpm -ql cloudstack-ui 2>/dev/null)"\n  index="$(awk '/\\/index\\.html$/ {print; exit}' <<<"$ui_files")"\n'''
count = s.count(old)
if count != 1:
    raise SystemExit(f'ERROR: expected exactly one v2 UI-root pipeline; found {count}.')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
PY

bash -n "$PATCHED"

grep -Fq 'ui_files="$(rpm -ql cloudstack-ui 2>/dev/null)"' "$PATCHED" \
  || { echo 'ERROR: pipefail-safe UI-root patch verification failed.' >&2; exit 1; }

exec "$PATCHED"

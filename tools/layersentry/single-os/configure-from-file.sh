#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
Usage:
  configure-from-file.sh validate INTENT.json
  configure-from-file.sh plan INTENT.json
  configure-from-file.sh apply INTENT.json CONFIRMED_PLAN_SHA256

CloudStack must attach the requested data volumes to this VM before 'plan' or
'apply'. This guest script never creates or attaches CloudStack volumes. It can
only initialize confirmed, already-attached non-OS devices into LVM/filesystems.

The intent file must use secret:// references. Do not store plaintext passwords
or join tokens in the JSON file.
EOF
}

[[ $# -ge 2 ]] || { usage; exit 2; }
mode="$1"
intent="$2"
[[ -f "$intent" && ! -L "$intent" ]] || { echo "intent must be a regular non-symlink file" >&2; exit 1; }

case "$mode" in
  validate)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    exec /usr/bin/layersentryctl validate-config "$intent"
    ;;
  plan)
    [[ $# -eq 2 ]] || { usage; exit 2; }
    cat >&2 <<'EOF'
PLAN ONLY: no provider mutation will start. Review every step, especially
lvm-pv-initialize, lvm-format, VIP and exact package/repository pins. Keep the
returned confirmation_digest for the apply command.
EOF
    exec /usr/bin/layersentryd plan-file "$intent"
    ;;
  apply)
    [[ $# -eq 3 ]] || { usage; exit 2; }
    digest="$3"
    [[ "$digest" =~ ^[0-9a-f]{64}$ ]] || { echo "confirmed plan digest must be 64 lowercase hex characters" >&2; exit 1; }
    cat >&2 <<'EOF'
APPLY: this may initialize confirmed LVM PVs and format confirmed filesystems.
The LayerSentry root-disk ancestry checks remain mandatory and cannot be
bypassed by this script.
EOF
    exec /usr/bin/layersentryd apply-file "$intent" "$digest"
    ;;
  *) usage; exit 2 ;;
esac

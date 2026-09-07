#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT="$ROOT/agent"
ANSIBLE="$(cd "$ROOT/.." && pwd)/ansible"

for cmd in go gofmt python3 ansible-playbook bash git gzip base64; do
  command -v "$cmd" >/dev/null || { echo "VALIDATION_FAIL missing_tool=$cmd" >&2; exit 1; }
done

pushd "$AGENT" >/dev/null
if [[ ! -f go.sum ]]; then
  echo "VALIDATION_FAIL committed_go_sum_missing" >&2
  echo "VALIDATION_INFO expected_module_lock_diff_follows" >&2
  go mod tidy -diff >&2 || true
  exit 1
fi
if ! go mod tidy -diff; then
  echo "VALIDATION_FAIL go_module_lock_not_tidy" >&2
  exit 1
fi

formatting_dirty=0
unformatted="$(gofmt -l .)"
if [[ -n "$unformatted" ]]; then
  formatting_dirty=1
  printf 'VALIDATION_INFO gofmt_required files:\n%s\n' "$unformatted" >&2
  gofmt -w .
  printf 'GOFMT_PATCH_B64_BEGIN\n'
  git diff --binary -- . | gzip -9 | base64 -w0
  printf '\nGOFMT_PATCH_B64_END\n'
fi

go test -count=1 ./...
go vet ./...
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
go build -trimpath -o "$tmp/layersentryd" ./cmd/layersentryd
go build -trimpath -o "$tmp/layersentryctl" ./cmd/layersentryctl
popd >/dev/null

find "$ANSIBLE/library" -type f -name '*.py' -print0 | xargs -0 -r python3 -m py_compile
find "$ROOT/acceptance" -type f -name '*.py' -print0 | xargs -0 -r python3 -m py_compile
if [[ -d "$ANSIBLE/tests" ]]; then
  python3 -m unittest discover -s "$ANSIBLE/tests" -p 'test_*.py'
fi

# Production uses private /run/layersentryd and /usr/lib/layersentry paths.
# Source validation runs unprivileged from the checkout, so override only the
# Ansible syntax-check working/search paths and leave production config intact.
mkdir -p "$tmp/ansible-local" "$tmp/ansible-remote"
chmod 0700 "$tmp/ansible-local" "$tmp/ansible-remote"
export ANSIBLE_CONFIG="$ANSIBLE/ansible.cfg"
export ANSIBLE_LOCAL_TEMP="$tmp/ansible-local"
export ANSIBLE_REMOTE_TEMP="$tmp/ansible-remote"
export ANSIBLE_ROLES_PATH="$ANSIBLE/roles"
export ANSIBLE_LIBRARY="$ANSIBLE/library"
export ANSIBLE_NOCOLOR=1
export ANSIBLE_FORCE_COLOR=0
export ANSIBLE_DISPLAY_ARGS_TO_STDOUT=false
for playbook in "$ANSIBLE"/playbooks/*.yml; do
  ansible-playbook --syntax-check -i "$ANSIBLE/inventory/localhost.ini" "$playbook" >/dev/null
done

while IFS= read -r -d '' script; do
  bash -n "$script"
done < <(find "$ROOT" -type f -name '*.sh' -print0)

if [[ "$formatting_dirty" -ne 0 ]]; then
  echo "VALIDATION_FAIL gofmt_changes_required; commit the emitted GOFMT_PATCH_B64 payload and rerun" >&2
  exit 1
fi

printf 'SINGLE_OS_SOURCE_VALIDATION_OK agent=%s ansible=%s\n' "$AGENT" "$ANSIBLE"

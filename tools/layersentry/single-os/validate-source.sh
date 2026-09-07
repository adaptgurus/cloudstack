#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT="$ROOT/agent"
ANSIBLE="$(cd "$ROOT/.." && pwd)/ansible"

for cmd in go python3 ansible-playbook bash; do
  command -v "$cmd" >/dev/null || { echo "VALIDATION_FAIL missing_tool=$cmd" >&2; exit 1; }
done

pushd "$AGENT" >/dev/null
unformatted="$(gofmt -l .)"
[[ -z "$unformatted" ]] || { printf 'VALIDATION_FAIL gofmt files:\n%s\n' "$unformatted" >&2; exit 1; }
go test -count=1 ./...
go vet ./...
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
go build -trimpath -o "$tmp/layersentryd" ./cmd/layersentryd
go build -trimpath -o "$tmp/layersentryctl" ./cmd/layersentryctl
popd >/dev/null

find "$ANSIBLE/library" -type f -name '*.py' -print0 | xargs -0 -r python3 -m py_compile

export ANSIBLE_CONFIG="$ANSIBLE/ansible.cfg"
export ANSIBLE_NOCOLOR=1
export ANSIBLE_FORCE_COLOR=0
export ANSIBLE_DISPLAY_ARGS_TO_STDOUT=false
for playbook in "$ANSIBLE"/playbooks/*.yml; do
  ansible-playbook --syntax-check -i "$ANSIBLE/inventory/localhost.ini" "$playbook" >/dev/null
done

while IFS= read -r -d '' script; do
  bash -n "$script"
done < <(find "$ROOT" -type f -name '*.sh' -print0)

printf 'SINGLE_OS_SOURCE_VALIDATION_OK agent=%s ansible=%s\n' "$AGENT" "$ANSIBLE"

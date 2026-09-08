#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
usage: module-writer-guard.sh start|check|precommit|advance MODULE [REMOTE] [BRANCH]

MODULE: k8s | single-os | dr | bootstrap | ui
REMOTE defaults to origin.
BRANCH defaults to layersentry/4.22.1.1-ui.

start     fetches and records the current remote branch as this session's base.
check     fetches and fails if the remote branch gained changes in this module's
          owned paths since the recorded base.
precommit fails if any currently staged path is outside this module's writable
          fence. Run it after staging and before every module source commit.
advance   records the latest remote branch after the session has reconciled its
          own/foreign commits and is ready for the next batch.

This is collision/path-fence enforcement, not a distributed lock. It does not
replace fetch/review/reconcile before mutation. CI independently rechecks K8s
commit paths so a local guard cannot be treated as production evidence alone.
EOF
}

[[ $# -ge 2 && $# -le 4 ]] || { usage; exit 2; }
action="$1"
module="$2"
remote="${3:-origin}"
branch="${4:-layersentry/4.22.1.1-ui}"

case "$module" in
  k8s|single-os|dr|bootstrap|ui) ;;
  *) echo "WRITER_GUARD_FAIL reason=unknown_module module=$module" >&2; exit 2 ;;
esac

repo_root="$(git rev-parse --show-toplevel 2>/dev/null)" || {
  echo "WRITER_GUARD_FAIL reason=not_git_repository" >&2
  exit 2
}
cd "$repo_root"

git_dir="$(git rev-parse --git-dir)"
state_dir="$git_dir/layersentry-writer-guard"
mkdir -p "$state_dir"
state_file="$state_dir/${module}.base"

owned_path() {
  local p="$1"
  case "$module" in
    k8s)
      [[ "$p" == tools/layersentry/k8s/* || "$p" == docs/layersentry/evidence/k8s/* || "$p" == .github/workflows/layersentry-k8s-* ]]
      ;;
    single-os)
      [[ "$p" == tools/layersentry/single-os/* ||
         "$p" == docs/layersentry/evidence/single-os/* ||
         "$p" == .github/workflows/layersentry-single-os-* ||
         "$p" == tools/layersentry/ansible/playbooks/single_os_* ||
         "$p" == tools/layersentry/ansible/roles/postgresql/* ||
         "$p" == tools/layersentry/ansible/roles/mysql_family/* ||
         "$p" == tools/layersentry/ansible/roles/keyvalue/* ||
         "$p" == tools/layersentry/ansible/roles/nginx/* ||
         "$p" == tools/layersentry/ansible/roles/httpd/* ||
         "$p" == tools/layersentry/ansible/roles/tomcat/* ||
         "$p" == tools/layersentry/ansible/roles/nodejs/* ||
         "$p" == tools/layersentry/ansible/roles/runtime/* ||
         "$p" == tools/layersentry/ansible/roles/storage_lvm/* ||
         "$p" == tools/layersentry/ansible/roles/network_vip/* ]]
      ;;
    dr)
      [[ "$p" == tools/layersentry/dr* || "$p" == docs/layersentry/evidence/dr/* ]]
      ;;
    bootstrap)
      [[ "$p" == docs/layersentry/evidence/bootstrap/* ||
         "$p" == docs/layersentry/evidence/hypervisor/* ||
         "$p" == .github/workflows/layersentry-hypervisor-* ||
         "$p" == .github/workflows/layersentry-bootstrap-* ||
         "$p" == tools/layersentry/ansible/playbooks/bootstrap_* ||
         "$p" == tools/layersentry/ansible/playbooks/hypervisor_* ||
         "$p" == tools/layersentry/ansible/roles/hypervisor_*/* ||
         "$p" == tools/layersentry/ansible/roles/network_bridge/* ||
         "$p" == tools/layersentry/ansible/roles/firewall/* ||
         "$p" == tools/layersentry/ansible/roles/selinux/* ||
         "$p" == tools/layersentry/ansible/roles/control_plane_*/* ||
         "$p" == tools/layersentry/ansible/inventories/schema/* ]]
      ;;
    ui)
      [[ "$p" == ui/* || "$p" == docs/layersentry/evidence/ui/* ]]
      ;;
  esac
}

if [[ "$action" == "precommit" ]]; then
  mapfile -t staged < <(git diff --cached --name-only --diff-filter=ACMRD)
  if ((${#staged[@]} == 0)); then
    printf 'WRITER_GUARD_OK module=%s staged=0 action=precommit\n' "$module"
    exit 0
  fi

  foreign=()
  for p in "${staged[@]}"; do
    if ! owned_path "$p"; then
      foreign+=("$p")
    fi
  done

  if ((${#foreign[@]} > 0)); then
    printf 'FOREIGN_MODULE_EDIT module=%s stage=precommit\n' "$module" >&2
    printf 'forbidden_path=%s\n' "${foreign[@]}" >&2
    echo "action=unstage_foreign_paths_and_hand_to_owning_module" >&2
    exit 4
  fi

  printf 'MODULE_PATH_FENCE_OK module=%s staged=%d action=precommit\n' "$module" "${#staged[@]}"
  exit 0
fi

git fetch --quiet "$remote" "$branch"
remote_ref="refs/remotes/${remote}/${branch}"
remote_head="$(git rev-parse "$remote_ref")"

record_base() {
  printf '%s\n' "$remote_head" > "$state_file"
  printf 'WRITER_GUARD_BASE module=%s remote=%s branch=%s sha=%s\n' "$module" "$remote" "$branch" "$remote_head"
}

case "$action" in
  start|advance)
    record_base
    ;;
  check)
    [[ -f "$state_file" ]] || {
      echo "WRITER_GUARD_FAIL reason=no_session_base action=start_required module=$module" >&2
      exit 2
    }
    base="$(tr -d '[:space:]' < "$state_file")"
    git cat-file -e "${base}^{commit}" 2>/dev/null || {
      echo "WRITER_GUARD_FAIL reason=invalid_session_base module=$module base=$base" >&2
      exit 2
    }
    if [[ "$base" == "$remote_head" ]]; then
      printf 'WRITER_GUARD_OK module=%s base=%s remote_head=%s changed=0\n' "$module" "$base" "$remote_head"
      exit 0
    fi

    mapfile -t changed < <(git diff --name-only "$base..$remote_head")
    collisions=()
    for p in "${changed[@]}"; do
      if owned_path "$p"; then
        collisions+=("$p")
      fi
    done

    if ((${#collisions[@]} > 0)); then
      printf 'CONCURRENT_WRITER_DETECTED module=%s base=%s remote_head=%s\n' "$module" "$base" "$remote_head" >&2
      printf 'changed_owned_path=%s\n' "${collisions[@]}" >&2
      echo "action=fetch_inspect_reconcile_then_advance" >&2
      exit 3
    fi

    printf 'WRITER_GUARD_OK module=%s base=%s remote_head=%s foreign_changes=%d\n' "$module" "$base" "$remote_head" "${#changed[@]}"
    printf 'action=review_foreign_commits_before_mutation\n'
    ;;
  *) usage; exit 2 ;;
esac

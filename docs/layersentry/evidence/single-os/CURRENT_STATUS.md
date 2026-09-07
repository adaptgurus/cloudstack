# LayerSentry Single-OS — Current Status

**Role:** module-scoped volatile evidence checkpoint for VM-native Single-OS DBaaS/APaaS.  
**Global current-status authority:** `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md` **plus current evidence**, per `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`. This file is the Single-OS evidence component of that authority.  
**Stable architecture authority:** `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`.  
**Execution routing:** `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`.

Always fetch the actual current branch before acting. Do not reset to a SHA copied from this file.

## Current reconciled state — 2026-09-07

| Scope | Status | Current truth |
| --- | --- | --- |
| Target VM-native architecture | `DESIGN_DEFINED` | Go orchestration/control + Ansible Runner + versioned roles/playbooks |
| Existing Go Single-OS engine/providers | `PARTIAL` | substantial source exists under `tools/layersentry/single-os/agent/`; preserve the control-plane investment and migrate imperative guest execution rather than rewriting from zero |
| Ansible Single-OS execution tree | `PENDING` | `tools/layersentry/ansible/` was absent at the continuity audit; target roles/playbooks are not yet current implementation |
| Historical September 7 Go source-validation result | `UNKNOWN` | handoff referenced `2026-09-07-single-os-lvm-vip-provider-storage-source-validation.md`, but that file has no repository path history and was not present |
| `CI_VERIFIED` for Single-OS | `NOT_TESTED` | no qualifying reproducible Single-OS CI evidence established by the continuity audit |
| Rocky Linux 9 provider/runtime qualification | `NOT_TESTED` | source is not live proof |
| Real PostgreSQL multi-node HA/replication/failover | `NOT_TESTED` | requires real multi-node evidence |
| Real Keepalived VRRP failover | `NOT_TESTED` | requires real multi-node evidence |
| Production certification | `NOT_TESTED` | provider/security/backup/recovery/upgrade/performance gates remain |

## Existing source that must be preserved

Current branch source already includes a substantial Go module at:

`tools/layersentry/single-os/agent/`

including command entrypoints, API/auth/config, lifecycle/journal/idempotency/locking, secrets/backup, storage/LVM/mount/network/VIP/preflight helpers, provider capability logic, UI assets and database/application provider implementations.

Do not restart F0/F1 from scratch after a session reset. Inspect and reuse the current source.

## Selected migration target

The current execution contract selects:

```text
LayerSentry UI/API
 -> Go orchestration/control
 -> Ansible Runner / ansible-core
 -> versioned LayerSentry roles/playbooks
 -> Rocky Linux 9 guest
```

Go retains schema/authorization/plan confirmation/idempotency/lock/journal/secrets/inventory/result/evidence/recovery authority. Imperative guest package/configuration/LVM/SELinux/firewall/VIP/provider actions are to migrate to Ansible.

Target architecture is not implementation evidence. If `tools/layersentry/ansible/` is still absent, Ansible remains `PENDING`.

## Historical handoff warning

`2026-09-07-single-os-lvm-vip-provider-storage-handoff.md` is historical implementation context, not normal startup authority. Its claim that Go tests/vet/build passed referenced an evidence file that was never committed. Do not inherit that pass result.

Continuity audit:

`docs/layersentry/evidence/single-os/2026-09-07-single-os-continuity-authority-reconciliation.md`

## First unmet gates

1. inspect actual current branch/source;
2. create the bounded Go→Ansible Runner foundation and target Ansible tree;
3. migrate PostgreSQL standalone as the first complete provider vertical slice;
4. remove/deprecate duplicate imperative runtime execution only after equivalent Ansible behavior and tests exist;
5. run and persist fresh source validation for the exact branch, including Go tests/vet/build and Ansible syntax/lint/idempotency/negative checks;
6. only then consider `SOURCE_COMPLETE` for the bounded migrated slice;
7. run Rocky Linux 9 live provider acceptance separately before `LIVE_VERIFIED`.

## Continuity invariant

A new ChatGPT/Codex session must treat current Git source as implementation truth and this file as the Single-OS status evidence pointer. It must not infer that code disappeared because chat memory reset, and it must not infer that designed Ansible roles exist before the repository proves they do.

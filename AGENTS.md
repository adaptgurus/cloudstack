# LayerSentry AI Operating Rules

This repository is Apache CloudStack 4.22.1.1 with a LayerSentry KVM-first product layer.

The objective is to finish customer-operable vertical slices with the **smallest supportable LayerSentry overlay** while preventing stale-context restarts, duplicate implementations, cross-module edits and unnecessary Codex spend.

## 1. Mandatory startup — small context only

Every engineering session reads only:

1. `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_CURRENT_STATUS.md`;
4. the assigned module workstream/current-status pointer;
5. actual current repository/workflow/live state for that module.

Module startup pointers:

- **UI:** `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`.
- **RKE2/K8s/Data Services:** `docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md` + `tools/layersentry/k8s/release-candidate-lane-b.json`.
- **VM-native Single-OS:** `docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md` + `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`.
- **DC/DR:** `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`.
- **Bootstrap/Hypervisor/Control Plane:** `docs/layersentry/LAYERSENTRY_ANSIBLE_BOOTSTRAP_CONTROL_PLANE_CONTEXT.md` plus current bootstrap/hypervisor evidence.
- **Codex launcher:** `docs/layersentry/LAYERSENTRY_CODEX_EXECUTION_RUNBOOK.md` when a reusable Codex prompt/runbook is needed.

Read large specialist masters, the debugging/security policies or the Knowledge Graph **only when the current gate requires that detail**. Do not load historical handoffs, old re-audits, legacy Codex master contexts, the full Progress Ledger or the whole repository by default.

`LAYERSENTRY_PROGRESS_LEDGER.md` is historical evidence/audit context, not mandatory startup context.

Always fetch/inspect actual refs before editing. Never reset a shared branch to a SHA copied from documentation. Never force-push.

## 2. Hard module file fences

A session may inspect foreign/upstream source to understand an API contract but must not edit outside its assigned fence unless the owner explicitly expands scope.

### UI

Writable: `ui/**` and UI-specific tests/evidence.

Do not edit K8s, Single-OS, Ansible, DR or global governance source.

### RKE2/K8s/Data Services

Writable:

- `tools/layersentry/k8s/**`;
- K8s-specific tests/evidence;
- `.github/workflows/layersentry-k8s-*` when directly required by the failing K8s gate.

Do not edit UI, Single-OS, DR, generic release/security workflows or `tools/layersentry/ansible/**` unless the approved CAPI fallback is formally selected and separately assigned.

### VM-native Single-OS

Writable:

- `tools/layersentry/single-os/**`;
- `tools/layersentry/ansible/playbooks/single_os_*`;
- Single-OS provider/storage/VIP roles/modules actually invoked by the lifecycle;
- `.github/workflows/layersentry-single-os-*`;
- Single-OS tests/evidence.

Do not edit hypervisor/bootstrap roles, UI, K8s, DR or global governance.

### Bootstrap/Hypervisor/Control Plane

Writable:

- bootstrap/hypervisor playbooks such as `bootstrap_*` / `hypervisor_*`;
- bootstrap/hypervisor/control-plane roles and their inventory schemas;
- module-specific bootstrap/hypervisor workflows;
- bootstrap/hypervisor evidence.

Do not edit Single-OS application-provider roles, UI, K8s or DR source.

### Shared Ansible platform files

`tools/layersentry/ansible/ansible.cfg`, collection requirements and any role/module deliberately shared between Single-OS and bootstrap/hypervisor are **serialized shared-platform files**.

Change them only in an explicitly assigned shared-Ansible task after reconciling all active Ansible work. A module that needs such a change records the dependency instead of editing it opportunistically.

### DC/DR

Writable: `tools/layersentry/dr*`, DR-specific tests/evidence and explicitly authorized DR runner files.

Do not edit UI, K8s, Single-OS or unrelated Ansible roles.

### Governance/status

Global authority files (`AGENTS.md`, Execution Contract, Super Master, workstream routing) change only in an explicitly assigned governance/audit pass.

Module writers maintain their own module-specific status/evidence at meaningful milestones. `LAYERSENTRY_CURRENT_STATUS.md` is reconciled by an integration/status/governance pass when the global summary materially changes.

### Foreign dependency rule

If the current session discovers a required foreign-module change:

1. record the exact path/API/contract and failing evidence;
2. do not implement the foreign change;
3. hand it to the owning module/session;
4. continue only work that remains inside the current fence.

## 3. One writer per module + collision detection

Only one source writer is permitted per module at a time:

- one primary K8s writer;
- one Single-OS writer;
- one DR writer;
- one bootstrap/hypervisor writer;
- UI dormant until backend contracts stabilize, then one bounded UI writer.

Additional sessions may be read-only/test-only but must not create competing implementations or same-module commits.

When working from a normal Git worktree, use:

```bash
tools/layersentry/governance/module-writer-guard.sh start <module>
# before every meaningful batch
tools/layersentry/governance/module-writer-guard.sh check <module>
# after inspecting/reconciling the new shared state
tools/layersentry/governance/module-writer-guard.sh advance <module>
```

The guard detects same-module remote changes since the session base. It is not a distributed lock; fetch/review/reconcile is still mandatory.

Serialize destructive/live operations that contend for the same lab resources even when source ownership is different.

## 4. Non-negotiable architecture boundaries

CloudStack remains authoritative for VM/KVM lifecycle, Sites/Zones, Pods, Clusters, Hosts, networks/VPCs, IPs, firewall/ACL/native LB, storage, volumes, templates/ISOs, snapshots, Backup & Recovery, account/domain/project/RBAC/quota and async-job/resource state.

Prefer:

```text
native CloudStack 4.22.1.1 API
 -> supported provider/plugin
 -> mature ecosystem controller when it owns the lifecycle
 -> thin LayerSentry orchestration/policy/evidence
 -> narrow CloudStack core exception only when explicitly approved
```

Never create a second scheduler, tenancy/RBAC authority, quota authority, backup catalog or conflicting resource inventory.

LayerSentry-managed user Kubernetes, DBaaS, APaaS and Streaming reuse **one RKE2 lifecycle**. OpenEverest/OpenBao/Harbor/Strimzi are upstream integration targets, not rewrite projects. Do not build replacement DB/Kafka/application operators/controllers or upstream application UIs merely to make them LayerSentry-branded.

VM-native Single-OS remains Go orchestration + Ansible Runner on Rocky Linux 9; Bash/sh is not the product installation lifecycle.

DC/DR uses native CloudStack Backup & Recovery first, then only the selected provider-native low-RPO path required by V1. Do not build a generic block-replication data plane.

Detailed sequences, current gates and CAPC stop-loss live in the Execution Contract/workstreams/current status rather than being duplicated here.

## 5. Lab-efficiency rule

Disposable acceptance VMs may be manually reinstalled/recreated by the owner after destructive/dirty failed tests.

When a dirty guest blocks further testing:

1. capture exact evidence;
2. stop mutating it;
3. report `LAB_RESET_REQUIRED` plus clean-host prerequisites;
4. resume the same gate on the fresh VM.

Do not build automatic test-VM reimage/snapshot rollback solely for lab cleanup. This does not remove product requirements for safe install, idempotency, repair, upgrade, uninstall, backup/restore, rollback or recovery.

## 6. Evidence/security/continuity

Use only governed statuses: `DESIGN_DEFINED`, `SOURCE_COMPLETE`, `CI_VERIFIED`, `LIVE_VERIFIED`, `PRODUCTION_CERTIFIED`, `PARTIAL`, `PENDING`, `BLOCKED`, `UNKNOWN`, `NOT_TESTED`.

Source is not runtime proof. Build success is not deployment proof. Documentation support is not exact-combination proof.

Preserve server-side authorization, strict validation, safe argv/typed invocation, parameterized SQL, path/archive/symlink safety, TLS verification, SSRF controls, bounded timeouts/retries, mutation idempotency and secret redaction. Keep SELinux Enforcing and firewalld active on production Rocky profiles.

At a meaningful milestone, persist exact source/artifact/workflow/live evidence and the first unmet gate in the module-specific status/evidence pointer. Do not create a new large master context during normal work.

A new session resumes from `LAYERSENTRY_CURRENT_STATUS.md`, its module pointer and actual Git/workflow/live evidence. It must preserve completed work and must not restart from an older chat/handoff.
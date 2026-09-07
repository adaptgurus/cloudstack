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

### 1.1 Hard context/credit-efficiency rules

These rules reduce repeated AI/Codex spend without weakening required production validation:

1. **Delta-first:** after startup, inspect the current gate, relevant paths and changes since the last verified evidence before broad repository reading. A whole-repository rescan is reserved for an explicitly assigned repository-level audit or when ownership/dependency discovery genuinely requires it.
2. **No repeated unchanged reads:** within one session, do not repeatedly reload unchanged master contexts, workstreams or large source files. Re-read only the changed section/ref or when a concurrent commit invalidates the prior view.
3. **Targeted retrieval first:** use exact paths, code search, diffs, focused logs and evidence pointers before loading large documents or full workflow logs.
4. **No duplicate reasoning artifacts:** do not create a new master context, handoff, architecture document, recap or audit copy when an existing canonical file can be updated or referenced.
5. **No unchanged expensive retries:** after one confirmatory rerun, do not repeat the same failing CI/lab/E2E action unless code, configuration, artifacts, environment state or the diagnostic hypothesis materially changed. Record the blocker/evidence instead. Rewording the same hypothesis is not a material change.
6. **Progressive validation:** use the cheapest validation that can falsify the current change first (focused source/static/unit/module checks), then the required integration/live/destructive gate. This is sequencing, not permission to skip E2E or production-certification evidence.
7. **Raw logs stay raw:** persist compact findings, identifiers, hashes, failure signatures and evidence pointers; do not paste large logs into startup/master documents.
8. **One implementation/diagnostic owner:** read-only/test-only parallelism is allowed when useful, but never pay multiple writers or diagnostic agents to independently solve the same module/gate/failure.
9. **Stop at a real external blocker:** when the next step requires a foreign-module change, lab reset, missing infrastructure, unavailable credential/resource or manual operator action, persist the exact blocker instead of generating speculative replacement code.
10. **Prefer deletion/reuse over abstraction:** a new shared framework is justified only when it removes duplicated active implementations and does not create a second authority for state, lifecycle, RBAC, quota, backup or inventory.
11. **Current-gate only:** do not debug, build or qualify a higher gate while the first unmet prerequisite is still failing. Inspect a higher layer only when evidence is required to classify the current failure.
12. **CI-noise filter:** inspect the module-specific workflow and the exact generic/release workflow required by the current gate. Do not spend model turns diagnosing unrelated CloudStack/UI/license/build failures merely because they ran on the same shared-branch commit.
13. **Bounded diagnostics first:** start with the smallest time window/object set that can classify the failure. Prefer exact conditions/events, focused command output and roughly the last 100-200 relevant log lines per component before expanding. Do not default to unbounded `journalctl`, whole-cluster YAML dumps, `kubectl get all -A -o yaml`, full database logs or full workflow logs.
14. **No unchanged rebuild/poll loops:** reuse an already verified immutable artifact when source, dependency locks/manifests, build recipe and artifact digest inputs are unchanged. Do not consume model turns repeatedly polling unchanged CI/lab state; query status when the next dependent action actually needs it.
15. **Mechanically guard expensive retries:** after an expensive CI/lab/E2E/destructive attempt fails, use `tools/layersentry/governance/expensive_retry_guard.py` as described below before another equivalent attempt.

Credit efficiency must never be used to mark an unexecuted production gate as passed.

### 1.2 Expensive retry guard

The retry guard stores local state only under `.git/layersentry-retry-guard/`; it does not create repository/status churn.

After an expensive attempt fails, record the compact fingerprint:

```bash
python3 tools/layersentry/governance/expensive_retry_guard.py record \
  --module <k8s|single-os|dr|bootstrap|ui> \
  --gate <stable-gate-id> \
  --artifact-digest <sha256-or-stable-id> \
  --environment-fingerprint <stable-hash-or-id> \
  --failure-signature <short-sanitized-signature> \
  --hypothesis <stable-material-hypothesis-id> \
  --result fail \
  --evidence <run-or-evidence-id>
```

Before rerunning that same expensive gate:

```bash
python3 tools/layersentry/governance/expensive_retry_guard.py check \
  --module <module> \
  --gate <stable-gate-id> \
  --artifact-digest <same-current-value> \
  --environment-fingerprint <same-current-value> \
  --failure-signature <same-current-value> \
  --hypothesis <same-current-value>
```

The source SHA defaults to current `HEAD`. The guard allows one unchanged confirmatory retry after the first failed attempt. After two failures with the same material fingerprint it exits with `UNCHANGED_EXPENSIVE_RETRY_BLOCKED`; do not bypass it. Change source/artifact/environment or a genuinely different diagnostic hypothesis, or record the gate as blocked.

After the gate succeeds, clear its local failure state:

```bash
python3 tools/layersentry/governance/expensive_retry_guard.py record \
  --module <module> --gate <stable-gate-id> \
  --artifact-digest <current-value> \
  --environment-fingerprint <current-value> \
  --failure-signature <current-value> \
  --hypothesis <current-value> \
  --result pass
```

Use only compact sanitized identifiers/hashes in retry-guard arguments; never put credentials, tokens, private keys, raw secrets or large logs into the local state.

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

## 3. One writer per module + collision/path enforcement

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
# after staging and before every module source commit
tools/layersentry/governance/module-writer-guard.sh precommit <module>
# after inspecting/reconciling the new shared state
tools/layersentry/governance/module-writer-guard.sh advance <module>
```

`precommit` fails closed with `FOREIGN_MODULE_EDIT` when the staged set crosses the module's writable fence. Unstage the foreign path and hand it to the owning module; do not bypass the guard. K8s commits are additionally rechecked by the module-specific CI path fence and source-validation workflow.

The guard detects same-module remote changes since the session base and staged cross-module edits. It is not a distributed lock; fetch/review/reconcile is still mandatory.

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

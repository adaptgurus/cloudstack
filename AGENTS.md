# LayerSentry AI Operating Rules

This repository is Apache CloudStack 4.22.1.1 with a LayerSentry KVM-first product layer.

The objective is to finish customer-operable vertical slices with the **smallest supportable LayerSentry overlay**, while preventing AI sessions from spending time or Codex credits on unrelated modules, stale context, duplicate implementations or lab-only automation.

## 1. Minimal startup

Every session reads only:

1. `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. the minimal module context below;
5. actual current repository/workflow/live state for that module.

Minimal module context:

- **UI:** `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`.
- **RKE2/K8s/Data Services:** `docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md` plus current `tools/layersentry/k8s/release-candidate-lane-b.json`. Read `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` / architecture addendum only when the current gate requires detailed storage/network/provider/version architecture or a conflict must be resolved.
- **VM-native Single-OS:** `docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md` plus `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`. Read the Single-OS Super Master only when a provider/architecture conflict requires it.
- **DC/DR:** `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`. Read `LAYERSENTRY_DRAAS_ARCHITECTURE.md` only for provider/failover semantics not already covered by the current gate.
- **Bootstrap/Hypervisor/Control Plane:** `docs/layersentry/LAYERSENTRY_ANSIBLE_BOOTSTRAP_CONTROL_PLANE_CONTEXT.md`.
- **Debugging/security:** read `LAYERSENTRY_DEBUGGING_RUNBOOK.md` or `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md` only when the current failure/trust boundary requires them.

Do **not** load historical handoffs, old re-audits, legacy Codex master contexts, every workstream, the Knowledge Graph, or the whole repository by default.

If the Progress Ledger contains an older embedded read order or historical owner/workstream label, this `AGENTS.md` plus the current Execution Contract supersede it. Historical checkpoint ownership text is evidence history, not permission to reactivate an old workstream.

Always inspect actual refs before editing. Never reset a shared branch to a SHA copied from documentation and never force-push.

## 2. Hard module file fences

A session may inspect CloudStack/upstream source outside its fence to understand a contract, but it must **not edit outside its assigned fence** unless the owner explicitly expands scope.

### UI

Writable:

- `ui/**`;
- UI-specific tests/evidence.

Do not edit K8s, Single-OS, Ansible, DR or global authority source. Generic release/build workflows belong to a milestone release task, not the UI writer.

### RKE2/K8s/Data Services

Writable:

- `tools/layersentry/k8s/**`;
- K8s-specific tests/evidence;
- `.github/workflows/layersentry-k8s-*` when such a module-specific workflow is directly required by the failing K8s gate.

Do not edit `ui/**`, Single-OS, DR, generic release workflows or `tools/layersentry/ansible/**` unless the approved CAPI fallback is formally selected and a separate fallback implementation scope is assigned.

### VM-native Single-OS

Writable:

- `tools/layersentry/single-os/**`;
- `tools/layersentry/ansible/playbooks/single_os_*`;
- Single-OS provider roles/modules actually invoked by the Single-OS lifecycle;
- `.github/workflows/layersentry-single-os-*`;
- Single-OS tests/evidence.

Normal Single-OS provider-role scope includes current provider/storage/VIP roles such as `postgresql`, `mysql_family`, `keyvalue`, `nginx`, `httpd`, `tomcat`, `nodejs`, `runtime`, `storage_lvm`, `network_vip` and their purpose-built Single-OS modules. Do not edit hypervisor/bootstrap roles.

### Bootstrap/Hypervisor/Control Plane

Writable:

- bootstrap/hypervisor playbooks such as `bootstrap_*` and `hypervisor_*`;
- bootstrap/hypervisor roles such as `hypervisor_*`, `network_bridge`, `firewall`, `selinux` and related host-preflight/inventory schema files;
- `.github/workflows/layersentry-hypervisor-*` / bootstrap-specific workflows when present;
- bootstrap/hypervisor evidence.

Do not edit Single-OS application-provider roles, UI, K8s or DR source.

### Shared Ansible platform files

Files such as `tools/layersentry/ansible/ansible.cfg`, `collections/requirements.yml` and any role/module intentionally shared by both Single-OS and bootstrap/hypervisor are **shared platform files**, not casually writable by either module.

Change them only under an explicitly assigned shared-Ansible task after fetching/reconciling all active Ansible work. A module that needs such a change records the dependency instead of silently editing a shared file during unrelated provider work.

### DC/DR

Writable:

- `tools/layersentry/dr*`;
- DR-specific tests/evidence;
- explicitly authorized DR runner files in the runner repository.

Do not edit UI, K8s, Single-OS or unrelated Ansible roles.

### Governance

Writable only during an explicitly assigned governance/audit pass:

- `AGENTS.md`;
- execution/master/workstream authority files.

Normal module agents do not modify governance files to document routine work.

### Cross-module dependency rule

If a session discovers a required foreign-module change:

1. record exact path/API/contract and failing evidence;
2. do not implement the foreign change;
3. hand it to the owning module/session;
4. continue only in-fence work.

This is a hard credit/concurrency rule.

## 3. One active writer per module

Use one source-writing session per module at a time:

- one primary RKE2/K8s writer;
- one Single-OS writer;
- one DR writer;
- one bootstrap/hypervisor writer;
- UI dormant until backend contracts stabilize, then one bounded final UI writer.

Additional sessions may be read-only/test-only but must not create parallel implementations or commits to the same module source.

## 4. CloudStack boundary

CloudStack remains authoritative for VM/KVM lifecycle, Zones/Sites, Pods, Clusters, Hosts, networks/VPCs, IPs, firewall/ACL/native LB, storage, volumes, templates/ISOs, snapshots, Backup & Recovery, account/domain/project/RBAC/quota and async-job/resource state.

Prefer in order:

1. native CloudStack 4.22.1.1 APIs;
2. supported CloudStack provider/plugin/configuration;
3. mature ecosystem controllers when they own the lifecycle;
4. thin LayerSentry orchestration/policy/evidence;
5. narrow CloudStack core change only by explicit exception.

Never create a second VM scheduler, tenancy/RBAC authority, quota authority, backup catalog or conflicting resource inventory.

## 5. RKE2/Kubernetes rule

Use one lifecycle for user Kubernetes, DBaaS, APaaS and Streaming:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> central Flux
 -> selected upstream packages/operators
```

The branch already contains substantial E0/E1 source. The K8s writer works the **first failing live gate**, not new horizontal scaffolding:

```text
immutable artifacts
 -> controller deployment
 -> cluster create
 -> automatic RKE2 join
 -> 6443 + 9345
 -> one primary CNI
 -> CCM
 -> one safe CSI path
 -> Flux remote reconciliation
 -> status/scale
 -> replacement + PVC/data survival
 -> delete
 -> restart/UNKNOWN reconciliation
 -> supported upgrade
 -> air-gap proof where claimed
```

### CAPC stop-loss

Do not patch CAPC indefinitely. If a bounded qualification campaign cannot achieve CloudStack VM creation + automatic join + 6443/9345 + `Ready`, and evidence shows downstream maintenance is disproportionate, record a release decision and switch to the approved native CloudStack API + QCOW2/cloud-init + Ansible Runner + RKE2 + Flux fallback. One release has one lifecycle owner.

### Existing healthy RKE2 package-test cluster

A separately provided healthy RKE2 cluster is a **test-only package lane** for Flux, OpenEverest, OpenBao, Harbor, Strimzi, backup/restore and offline package tests.

It does not edit lifecycle source and its results do **not** by themselves promote the full LayerSentry K8s/DBaaS stack to `LIVE_VERIFIED`. Full LayerSentry live qualification still requires the same pinned package on the LayerSentry-owned cluster path with the certified storage/network/project boundaries. Package-lane failures are handed to the primary K8s writer.

## 6. Upstream-service rule

For V1 use mature upstream products:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- OpenBao from supported Helm/OCI content;
- Harbor from supported Helm/OCI content;
- Strimzi for Kafka.

Do not build replacement DB operators, backup/PITR engines, DB failover engines, Kafka operators, Harbor/OpenBao controllers or replacement upstream UIs. Upstream service UI rebranding is out of V1 unless explicitly assigned.

## 7. VM-native Single-OS rule

Architecture:

```text
LayerSentry UI/API
 -> Go orchestration/control
 -> Ansible Runner / ansible-core
 -> versioned roles/playbooks
 -> Rocky Linux 9 VM
```

Go owns authorization, validation, planning, idempotency/locking, durable state/journal, secrets, execution/result handling and recovery state. Ansible owns guest package/configuration/service/SELinux/firewalld/LVM/network/VIP/provider work.

Do not implement product lifecycle as Bash/sh. Existing runtime shell lifecycle assets are deprecated.

### Disposable lab reset optimization

For V1 test-environment reset only, the owner may manually reinstall/recreate a disposable Rocky Linux 9 VM after a destructive/dirty failed test.

Capture evidence, stop mutating the dirty guest, report `LAB_RESET_REQUIRED`, then resume the same gate on the fresh VM. Do not spend engineering/Codex effort building automatic lab reimage/snapshot rollback solely for cleanup.

This does not remove product requirements for safe install, idempotency, repair, upgrade, uninstall, backup/restore or recovery.

## 8. DC/DR rule

Native CloudStack recovery is the V1 critical path:

```text
healthy DC/DR CloudStack
 -> native Backup & Recovery
 -> OLD recovery point
 -> mutate data
 -> NEW recovery point
 -> selected createVMFromBackup recovery
 -> isolated destination network
 -> exact root/data validation
 -> negative/retry/RBAC
 -> thin LayerSentry orchestration
```

Only after native recovery works should one selected provider-native low-RPO path be added. Do not build a generic LayerSentry block replication engine when CloudStack/storage providers already expose the data plane.

## 9. UI and release activation

Do not keep a UI Codex session active while backend contracts move. Freeze UI except for a blocking integration defect, then run one bounded final UI acceptance/fix pass after K8s, DR and Single-OS contracts stabilize.

Release/signing/security work is milestone-gated, not a permanent parallel stream. Generic release workflows/tooling are changed only by the assigned milestone owner.

## 10. Evidence, security and handoff

Use only governed statuses: `DESIGN_DEFINED`, `SOURCE_COMPLETE`, `CI_VERIFIED`, `LIVE_VERIFIED`, `PRODUCTION_CERTIFIED`, `PARTIAL`, `PENDING`, `BLOCKED`, `UNKNOWN`, `NOT_TESTED`.

Source is not runtime proof. Build success is not deployment proof. Documentation is not exact-combination proof.

Preserve server-side authorization, strict validation, safe argv/typed invocation, parameterized SQL, path/archive/symlink safety, TLS verification, SSRF controls, finite timeouts/retries, mutation idempotency and secret redaction. Keep SELinux Enforcing and firewalld active on production Rocky profiles.

Handoffs are concise: exact branch/commit, files changed, tests/live actions, first unmet gate, exact next action. Do not create a new large master context after normal module work.

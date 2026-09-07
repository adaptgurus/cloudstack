# LayerSentry AI Operating Rules

This repository is Apache CloudStack 4.22.1.1 with a LayerSentry KVM-first product layer.

The objective is to finish customer-operable vertical slices with the **smallest supportable LayerSentry overlay**, while preventing AI sessions from spending time or Codex credits on unrelated modules.

## 1. Minimal startup

Before changing source or runtime, read only:

1. `AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. exactly one specialist context/workstream for the assigned module;
5. fetch the actual current repository/workflow/live state.

Specialist context:

- UI: `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`;
- RKE2/Kubernetes/Data Services: `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` + `docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`;
- VM-native Single-OS: `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` + `docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`;
- DC/DR: `docs/layersentry/LAYERSENTRY_DRAAS_ARCHITECTURE.md` + `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`;
- bootstrap/hypervisor/control-plane HA: `docs/layersentry/LAYERSENTRY_ANSIBLE_BOOTSTRAP_CONTROL_PLANE_CONTEXT.md`.

Do not load historical handoffs, old re-audits, unrelated workstreams or the whole repository by default.

Always inspect actual refs before editing. Never reset a shared branch to a SHA copied from documentation and never force-push.

## 2. Hard module file fences

A session may inspect CloudStack source outside its fence when required to understand a native API/contract, but it must **not edit outside its assigned fence** unless the owner explicitly expands scope.

| Module | Normal writable paths | Do not edit from this module |
| --- | --- | --- |
| UI | `ui/**`, UI-specific tests/evidence | `tools/layersentry/k8s/**`, `tools/layersentry/single-os/**`, `tools/layersentry/ansible/**`, `tools/layersentry/dr*` |
| RKE2/K8s/Data Services | `tools/layersentry/k8s/**`, K8s-specific tests/evidence, exact K8s artifact/workflow files when required | `ui/**`, `tools/layersentry/single-os/**`, `tools/layersentry/ansible/**` unless an approved fallback is activated, `tools/layersentry/dr*` |
| VM-native Single-OS | `tools/layersentry/single-os/**`, Single-OS Ansible playbooks/roles/modules and Single-OS evidence | `ui/**`, `tools/layersentry/k8s/**`, `tools/layersentry/dr*`, hypervisor/bootstrap roles unless explicitly assigned |
| DC/DR | `tools/layersentry/dr*`, DR-specific tests/evidence, authorized DR runner files | `ui/**`, `tools/layersentry/k8s/**`, `tools/layersentry/single-os/**`, unrelated Ansible provider roles |
| Bootstrap/Hypervisor/Control Plane | bootstrap/hypervisor Ansible playbooks/roles, bootstrap evidence | Single-OS application-provider roles, `ui/**`, `tools/layersentry/k8s/**`, `tools/layersentry/dr*` |
| Governance | `AGENTS.md`, execution/master/workstream authority files | product/runtime source unless separately assigned |

Module agents do not edit `AGENTS.md`, Super Master Context, execution routing or another workstream merely to document their work. Stable authority changes belong to a dedicated governance pass.

### Cross-module dependency rule

If a session discovers a required change outside its fence:

1. record the exact required path/API/contract and failing evidence;
2. do not implement the foreign-module change;
3. hand it to the owning module/session;
4. continue only work that remains inside the current fence.

This is a hard credit/concurrency rule, not a suggestion.

## 3. One active writer per module

Use one source-writing session per module at a time.

- one primary RKE2/K8s writer;
- one Single-OS writer;
- one DR writer;
- one bootstrap/hypervisor writer;
- UI remains dormant until backend contracts are stable, then one bounded final UI writer.

Additional sessions may perform **read-only/test-only** qualification on separate targets but must not create parallel implementations.

## 4. CloudStack boundary

CloudStack remains authoritative for VM/KVM lifecycle, Zones/Sites, Pods, Clusters, Hosts, networks/VPCs, IPs, firewall/ACL/native LB, storage, volumes, templates/ISOs, snapshots, Backup & Recovery, account/domain/project/RBAC/quota and async-job/resource state.

Prefer in order:

1. native CloudStack 4.22.1.1 APIs;
2. supported CloudStack provider/plugin/configuration;
3. mature Kubernetes ecosystem controllers when Kubernetes owns lifecycle;
4. thin LayerSentry orchestration/policy/evidence;
5. narrow CloudStack core change only by explicit exception.

Never create a second VM scheduler, tenancy/RBAC authority, quota authority or backup/resource inventory.

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

The branch already contains substantial E0/E1 source. The K8s writer must work the **first failing live gate**, not add horizontal scaffolding.

Required order:

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

### Existing RKE2 package-test cluster

A separately provided healthy RKE2 cluster may be used in parallel as a **test-only package qualification lane** for Flux, OpenEverest, OpenBao, Harbor, Strimzi, backup/restore and offline package tests.

That lane must not edit CAPI/CAPC/CAPRKE2 lifecycle source. If it discovers a source defect, it reports the exact failure to the primary K8s writer.

## 6. Upstream-service rule

For V1 use mature upstream products instead of rewriting them:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- OpenBao from supported Helm/OCI content;
- Harbor from supported Helm/OCI content;
- Strimzi for Kafka.

Do not build replacement DB operators, backup/PITR engines, DB failover engines, Kafka operators, Harbor/OpenBao controllers or replacement upstream UIs. Rebranding upstream service UIs is out of V1 unless explicitly assigned.

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

Do not implement product lifecycle as Bash/sh. Existing shell lifecycle assets are deprecated and must not be extended.

### Disposable lab reset optimization

For V1 **test-environment reset only**, the product owner may manually reinstall/recreate a disposable Rocky Linux 9 VM after a destructive/dirty failed test.

When a dirty guest blocks further acceptance:

1. capture failure evidence;
2. stop mutating that guest;
3. report `LAB_RESET_REQUIRED` with required clean-host prerequisites;
4. resume after the owner provides a fresh Rocky 9 VM.

Do **not** spend engineering/Codex effort building snapshot/reimage/automatic guest-reset machinery solely to clean the acceptance lab. This shortcut does not remove product requirements for safe install, idempotency, repair, upgrade, uninstall, backup/restore or rollback behavior.

## 8. DC/DR rule

Native CloudStack recovery is the V1 critical path:

```text
healthy DC/DR CloudStack
 -> native Backup & Recovery
 -> OLD recovery point
 -> mutate data
 -> NEW recovery point
 -> selected `createVMFromBackup` recovery
 -> isolated destination network
 -> exact root/data validation
 -> negative/retry/RBAC
 -> thin LayerSentry orchestration
```

Only after native recovery works should one selected provider-native low-RPO path be added. Do not build a generic LayerSentry block replication engine when CloudStack/storage providers already expose the data plane.

## 9. UI and release activation rule

Do not keep a UI Codex session continuously active while backend contracts are still changing. Freeze UI source except for a blocking integration defect, then run one bounded final UI acceptance/fix pass after K8s, DR and Single-OS backend contracts stabilize.

Release/signing/security work is milestone-gated, not a permanent parallel stream. Run it when a module has an artifact ready for promotion or when a concrete security blocker appears.

## 10. Evidence, security and handoff

Use only governed statuses: `DESIGN_DEFINED`, `SOURCE_COMPLETE`, `CI_VERIFIED`, `LIVE_VERIFIED`, `PRODUCTION_CERTIFIED`, `PARTIAL`, `PENDING`, `BLOCKED`, `UNKNOWN`, `NOT_TESTED`.

Source is not runtime proof. Build success is not deployment proof. Documentation is not exact-combination proof.

Preserve server-side authorization, strict validation, safe argv/typed invocation, parameterized SQL, path/archive/symlink safety, TLS verification, SSRF controls, finite timeouts/retries, mutation idempotency and secret redaction. Keep SELinux Enforcing and firewalld active on production Rocky profiles.

Handoffs are concise: exact branch/commit, files changed, tests/live actions, first unmet gate, exact next action. Do not create a new large master context after normal module work.
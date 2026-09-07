# LayerSentry V1 — Execution Contract

**Contract schema:** 1.2  
**Effective date:** 2026-09-07  
**Baseline:** Apache CloudStack 4.22.1.1 + KVM

This file defines **who works on what, when a workstream is active, and how to avoid wasting Codex credits**. `AGENTS.md` defines hard safety/file-fence rules. `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` defines stable product architecture.

## 1. Default execution routing

| Surface | Default owner | Activation |
| --- | --- | --- |
| RKE2/Kubernetes/Data Services | **Codex** | active primary technical stream |
| UI/Self-Service | **Codex** | **deferred bounded final pass**; no continuous UI stream while backend contracts move |
| VM-native Single-OS | **ChatGPT** | active as needed; Go + Ansible |
| DC/DR/DRaaS | **ChatGPT** | active native-API/lab stream |
| Bootstrap/Hypervisor/Control-plane HA | **ChatGPT** | active only when its lab/resources are available |
| Release/signing/security promotion | milestone-gated | activate only for an artifact/security gate, not as a permanent stream |
| Governance/context | ChatGPT | only when stable authority actually changes |

If the owner chooses Codex for a normally ChatGPT-owned module, the same file fences and activation rules still apply.

## 2. Session startup and credit discipline

Every session reads only:

1. `/AGENTS.md`;
2. this file;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. one specialist context/workstream;
5. current source/workflow/live state.

Do not read unrelated modules, old handoffs or full repository history without a concrete need.

A module session must not edit global authority files or another module. When it finds a foreign dependency, it creates a concise handoff to the owning module instead of fixing it itself.

## 3. Active-workstream schedule

The lowest-credit V1 schedule is:

```text
PRIMARY WRITER: RKE2/K8s
  -> close E0/E1 live gates
  -> reuse one lifecycle for user K8s/Data Services/APaaS/Streaming

PARALLEL TEST-ONLY LANE: existing healthy RKE2 cluster
  -> Flux/package qualification
  -> OpenEverest/OpenBao/Harbor/Strimzi
  -> no CAPI/CAPC lifecycle source edits

PARALLEL WRITER: Single-OS
  -> current Go+Ansible vertical slice
  -> use fresh disposable Rocky VMs for lab resets

PARALLEL WRITER: DR
  -> fix CloudStack/B&R/Zone/storage/KVM environment
  -> native OLD/NEW recovery before advanced DR source

OPTIONAL WRITER: bootstrap/hypervisor
  -> only when its dedicated lab is available

DEFERRED: UI
  -> one final integration/browser pass after backend contracts stabilize

MILESTONE ONLY: release/signing/security promotion
```

Do not activate additional writers merely because a workstream file exists.

## 4. RKE2/K8s execution contract

One lifecycle serves user K8s, DBaaS, APaaS and Streaming:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> Flux
 -> selected upstream packages/operators
```

The branch already has substantial BFF/auth/RBAC, reconciliation, CAPI/CAPC/CAPRKE2 resources, lifecycle executor, CAPC endpoint/volume work, CCM/CSI downstream work, NodeDiskSet, Flux resources and runtime wiring.

Therefore the primary K8s writer proceeds strictly:

```text
immutable artifacts
 -> controller deployment
 -> cluster create
 -> automatic join
 -> 6443/9345
 -> one CNI
 -> CCM
 -> one safe CSI path
 -> Flux remote reconcile
 -> status/scale
 -> replacement + PVC survival
 -> delete
 -> restart/UNKNOWN reconciliation
 -> supported upgrade
 -> air-gap proof where claimed
```

### CAPC stop-loss

If a bounded campaign repeatedly cannot achieve VM creation + automatic join + 6443/9345 + `Ready`, and evidence shows continued provider maintenance is disproportionate, select the approved release fallback:

```text
native CloudStack APIs -> QCOW2/cloud-init -> Ansible Runner -> RKE2 -> Flux
```

Do not maintain both lifecycle owners for the same release.

### Existing RKE2 test cluster

Use the separately provided working RKE2 cluster to qualify packages independently of CAPC. This can save time by proving Flux/OpenEverest/OpenBao/Harbor/Strimzi while the LayerSentry-created cluster path is still being fixed.

The package-test lane is read/test oriented. It reports package/manifests defects to the primary K8s writer rather than creating a second K8s implementation branch.

## 5. Kubernetes services

Use mature upstream lifecycle implementations:

- OpenEverest stable v1 for supported PostgreSQL/PXC-MySQL/MongoDB;
- OpenBao Helm/OCI;
- Harbor Helm/OCI;
- Strimzi for Kafka.

LayerSentry work is limited to pinned Flux/Helm integration, namespace/RBAC, StorageClass, network/VIP policy, local/offline artifact references, status/audit and E2E qualification.

Do not rewrite upstream operators/controllers, backup/PITR engines or upstream UIs. Rebranding upstream service UIs is not V1 scope unless explicitly reassigned.

## 6. VM-native Single-OS contract

Architecture:

```text
LayerSentry UI/API -> Go orchestration -> Ansible Runner -> Rocky Linux 9 guest
```

Preserve current source. Go owns planning/state/security; Ansible owns guest configuration.

### Manual disposable-VM reset

The product owner can manually reinstall/recreate test VMs. For V1 lab iteration, this is the default cleanup method after a destructive failed acceptance test.

An agent must not spend time building automated test-VM reimage/snapshot rollback solely to restore the lab. It records evidence, reports `LAB_RESET_REQUIRED`, waits for/uses the fresh Rocky VM, and resumes the same acceptance gate.

This is a **lab-efficiency shortcut only**. It does not remove customer-facing requirements for idempotency, repair, upgrade, uninstall, backup/restore or safe rollback behavior.

## 7. DC/DR contract

Use CloudStack-native operations first:

```text
healthy DC/DR infrastructure
 -> native B&R enabled/configured
 -> Recovery Point OLD
 -> mutate data
 -> Recovery Point NEW
 -> selected createVMFromBackup recovery
 -> isolated destination network
 -> exact root/data verification
 -> retry/RBAC/negative cases
 -> thin LayerSentry orchestration
```

Existing provider-neutral DR state source is retained but does not justify more framework work before native recovery passes.

After native recovery, implement only one selected provider-native low-RPO path required by the V1 target (for example LINSTOR/DRBD, Ceph RBD or certified SAN replication). Planned failover/failback precedes witness/fencing/automatic failover.

## 8. UI contract

The current UI is substantially implemented. Do not keep a UI writer active while K8s/DR/Single-OS backend contracts change.

Run one bounded final UI pass when the backend APIs are stable enough to validate:

- VM/bucket/backup/self-service flows;
- RKE2 create/status/scale/delete;
- Data Services/APaaS/Streaming catalog/status;
- DR recovery workflow;
- RBAC/routes/progress/errors;
- production build and browser acceptance.

No broad redesign or upstream-service UI rewrite.

## 9. Release/security contract

Use one logical signed V1 carrier: `layersentry-platform-<release>.iso`. Bundled packages are `AVAILABLE`; Flux installs only selected packages.

Do not run a permanent release/security agent. Activate release/signing/security work only when an exact artifact is ready for promotion or a concrete trust-boundary defect blocks a vertical slice.

## 10. Completion/stop rules

For any module:

1. work only the first unmet gate;
2. stop adding features while that gate is failing;
3. fix the smallest correct owner;
4. rerun the same gate;
5. checkpoint only meaningful milestones;
6. stop the session when it reaches a foreign-module dependency or needs a manual lab reset.

Progress is measured by customer-operable vertical slices, not commits, lines or documents.

## 11. Conflict rule

This contract supersedes older execution-routing and sequencing instructions where they conflict. Detailed specialist storage/network/security/data-safety architecture remains valid.
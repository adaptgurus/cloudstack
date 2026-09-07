# LayerSentry V1 — Execution Contract

**Contract schema:** 1.6  
**Effective date:** 2026-09-08  
**Baseline:** Apache CloudStack 4.22.1.1 + KVM

This file defines **workstream ownership, activation and gate order**. `AGENTS.md` owns hard file/safety/concurrency/credit-efficiency rules. `LAYERSENTRY_CURRENT_STATUS.md` owns compact current orientation. `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` owns stable product architecture.

## 1. Default execution routing

| Surface | Default owner | Activation |
| --- | --- | --- |
| RKE2/Kubernetes/Data Services | **Codex** | **active primary technical stream** |
| Healthy second RKE2 cluster | test-only | parallel package qualification when supplied |
| UI/Self-Service | **Codex** | deferred bounded final pass after backend contracts stabilize |
| VM-native Single-OS | **ChatGPT** | active when its lab is available |
| DC/DR/DRaaS | **ChatGPT** | active native-API/lab stream |
| Bootstrap/Hypervisor/Control-plane HA | **ChatGPT** | active when its dedicated lab/resources are available |
| Release/signing/security | milestone-gated | artifact/trust blocker or promotion gate only |
| Governance/status | ChatGPT | only when authority/current-status structure materially changes |

Explicit reassignment does not relax file fences, one-writer rules or stop conditions.

## 2. Session startup

Every session reads only:

1. `/AGENTS.md`;
2. this Execution Contract;
3. `LAYERSENTRY_CURRENT_STATUS.md`;
4. its assigned workstream/module status;
5. actual current source/workflow/live state.

The Progress Ledger, specialist masters, Knowledge Graph, security/debugging policies and historical handoffs are on-demand only. Follow the delta-first/targeted-retrieval/no-duplicate-retry rules in `AGENTS.md`; they are not repeated here.

## 3. Lowest-credit V1 schedule

```text
PRIMARY
  one RKE2/K8s Codex source writer
  -> first failing E0/E1 gate only

PARALLEL TEST-ONLY
  existing healthy RKE2 cluster
  -> Flux/OpenEverest/OpenBao/Harbor/Strimzi/offline package tests
  -> no lifecycle-source commits

PARALLEL
  one Single-OS ChatGPT writer
  -> current provider gate; manual disposable Rocky reset when needed

PARALLEL
  one DR ChatGPT writer
  -> healthy CloudStack + native B&R + OLD/NEW recovery first

OPTIONAL
  bootstrap/hypervisor ChatGPT
  -> only when its three-host lab/resources are available

DEFERRED
  one final UI Codex pass

MILESTONE ONLY
  release/signing/security
```

Do not activate additional writers merely because a workstream file exists.

## 4. RKE2 / Data Services contract

One lifecycle serves user Kubernetes and Kubernetes-backed DBaaS/APaaS/Streaming:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> Flux
 -> selected upstream packages/operators
```

Current source is already substantial. Work the first failing gate only:

```text
immutable artifacts
 -> controller deployment
 -> one real cluster
 -> automatic join
 -> 6443 + 9345
 -> Ready
 -> one CNI
 -> CCM
 -> one safe CSI path
 -> Flux
 -> status/scale
 -> replacement + PVC survival
 -> delete
 -> restart/UNKNOWN reconciliation
 -> supported upgrade
 -> air-gap proof where claimed
```

Do not add service breadth while the current substrate gate fails.

### Current K8s scope exclusions

Workstream E does **not** own or implement:

- VM-native Single-OS DBaaS/APaaS;
- cross-site RKE2 application DR;
- Kubernetes-backed DBaaS DC->DR replication/promotion/failback;
- APaaS cross-site DR;
- RKE2 failover/failback, RPO/RTO, cross-site DNS/VIP switching or RKE2 DR UI.

These are not K8s completion blockers unless the owner explicitly reopens scope. Independent DC/DR remains separate.

CSI/PVC project isolation, resize, stateful Machine replacement/PVC survival and DB backup/restore/PITR where advertised remain in scope because they are normal stateful-Kubernetes/DBaaS lifecycle capabilities, not cross-site DR.

### CAPC stop-loss

If a bounded campaign repeatedly cannot achieve CloudStack VM/resource creation + automatic RKE2 join + 6443/9345 + `Ready`, and evidence shows continued CAPC maintenance is disproportionate, record the release decision and assign:

```text
native CloudStack APIs -> QCOW2/cloud-init -> Ansible Runner -> RKE2 -> Flux
```

One release uses one cluster lifecycle owner.

### Upstream services

Use pinned/qualified OpenEverest, OpenBao, Harbor and Strimzi. LayerSentry integrates Flux/Helm/artifacts, namespace/RBAC, storage/network/VIP policy, status/audit and E2E evidence; it does not rewrite their lifecycle controllers, backup/PITR engines or UIs.

## 5. VM-native Single-OS contract

```text
LayerSentry UI/API -> Go orchestration -> Ansible Runner -> Rocky Linux 9 guest
```

Preserve the existing Go control plane and current Ansible provider tree. Work only the current provider's first unmet gate. Manual recreation of dirty disposable Rocky test VMs is preferred over lab-only reimage automation; customer-facing idempotency/repair/upgrade/uninstall/backup/restore requirements remain mandatory.

## 6. Independent DC/DR contract

```text
healthy DC/DR infrastructure
 -> native B&R
 -> Recovery Point OLD
 -> mutate data
 -> Recovery Point NEW
 -> selected createVMFromBackup
 -> isolated destination network
 -> exact OLD/NEW root/data verification
 -> retry/RBAC/negative cases
 -> thin LayerSentry orchestration
```

After native recovery, qualify only one required provider-native low-RPO path. Planned failover/failback precedes witness/fencing/automatic failover.

This independent workstream does not currently impose RKE2 application DR requirements on Workstream E.

## 7. UI / release activation

UI remains dormant while backend contracts move. Run one bounded final pass when real VM/K8s/Data Services/independent-DR contracts are stable enough for integration and browser acceptance.

Release/signing/security is not a standing stream. Activate it only for an exact artifact promotion/trust gate or concrete security blocker. One logical V1 carrier remains `layersentry-platform-<release>.iso`; bundled packages are `AVAILABLE`, not automatically installed.

## 8. Status and stop rules

Module writers update module-specific status/evidence after meaningful milestones. An integration/status pass updates `LAYERSENTRY_CURRENT_STATUS.md` when a module status, first unmet gate or authoritative pointer materially changes. Keep historical logs out of startup context.

For any module: work the first unmet gate, fix the smallest correct owner, rerun the same gate, and stop at a foreign-module dependency, manual lab reset or unavailable infrastructure/resource.

Progress is measured by customer-operable vertical slices, not commits, lines or document volume.

## 9. Conflict rule

This contract supersedes older execution-routing, startup-read-order and sequencing instructions where they conflict. Detailed specialist storage/network/security/data-safety architecture remains valid unless explicitly superseded.
# LayerSentry V1 — Execution Contract

**Contract schema:** 1.3  
**Effective date:** 2026-09-07  
**Baseline:** Apache CloudStack 4.22.1.1 + KVM

This file defines **who works on what and when a workstream is active**. `AGENTS.md` defines hard file/safety/concurrency rules. `LAYERSENTRY_CURRENT_STATUS.md` defines the compact current progress index. `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` defines stable product architecture.

## 1. Default execution routing

| Surface | Default owner | Activation |
| --- | --- | --- |
| RKE2/Kubernetes/Data Services | **Codex** | **active primary technical stream** |
| Healthy second RKE2 cluster | test-only | parallel package qualification when supplied |
| UI/Self-Service | **Codex** | **deferred bounded final pass** after backend contracts stabilize |
| VM-native Single-OS | **ChatGPT** | active when its lab is available |
| DC/DR/DRaaS | **ChatGPT** | active native-API/lab stream |
| Bootstrap/Hypervisor/Control-plane HA | **ChatGPT** | active when its dedicated lab/resources are available |
| Release/signing/security | milestone-gated | activate only for an artifact/trust blocker or promotion gate |
| Governance/status | ChatGPT | activate only when authority/current-status structure materially changes |

If the owner explicitly assigns Codex to a normally ChatGPT-owned module, all file fences, one-writer rules and stop conditions remain unchanged.

## 2. Session startup

Every session reads only:

1. `/AGENTS.md`;
2. this Execution Contract;
3. `LAYERSENTRY_CURRENT_STATUS.md`;
4. its assigned workstream/module status;
5. actual current source/workflow/live state.

The full `LAYERSENTRY_PROGRESS_LEDGER.md` is **not mandatory startup context**. It is read/search-on-demand for historical evidence only.

Large specialist masters, security/debugging policy, Knowledge Graph and historical handoffs are also on-demand only when the current gate requires them.

## 3. Lowest-credit V1 schedule

```text
PRIMARY SOURCE WRITER
  RKE2/K8s Codex
  -> first failing E0/E1 gate only

PARALLEL TEST-ONLY
  healthy existing RKE2 cluster
  -> Flux/OpenEverest/OpenBao/Harbor/Strimzi/offline package tests
  -> no lifecycle-source commits

PARALLEL SOURCE WRITER
  Single-OS ChatGPT
  -> current Go+Ansible provider gate
  -> manual disposable Rocky reset when needed

PARALLEL SOURCE/LAB WRITER
  DR ChatGPT
  -> healthy CloudStack + native B&R + OLD/NEW recovery first

OPTIONAL SOURCE/LAB WRITER
  bootstrap/hypervisor ChatGPT
  -> only when its three-host lab/resources are available

DEFERRED
  UI Codex
  -> one final backend integration/browser pass

MILESTONE ONLY
  release/signing/security
```

Do not activate additional writers merely because a workstream file exists.

## 4. RKE2 / Data Services execution contract

One lifecycle serves user Kubernetes, DBaaS, APaaS and Streaming:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> Flux
 -> selected upstream packages/operators
```

The current source already contains substantial BFF/auth/RBAC, durable reconciliation, CloudStack preflight/client, CAPI/CAPC/CAPRKE2 resources, lifecycle executor, dual-endpoint/volume-ownership work, CCM/CSI downstream source, NodeDiskSet, Flux and runtime wiring.

Therefore the primary writer works strictly:

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

### CAPC stop-loss

If a bounded qualification campaign repeatedly cannot achieve CloudStack VM creation + automatic RKE2 join + 6443/9345 + `Ready`, and evidence shows continued CAPC maintenance is disproportionate, record a release decision and assign the approved fallback:

```text
native CloudStack APIs -> QCOW2/cloud-init -> Ansible Runner -> RKE2 -> Flux
```

One release uses one cluster lifecycle owner.

### Upstream services

Use pinned/qualified OpenEverest, OpenBao, Harbor and Strimzi. LayerSentry integration is limited to Flux/Helm/artifacts, namespace/RBAC, storage/network/VIP policy, status/audit and E2E qualification. Do not rewrite their operators/controllers, backup/PITR engines or UIs.

## 5. VM-native Single-OS contract

Architecture:

```text
LayerSentry UI/API -> Go orchestration -> Ansible Runner -> Rocky Linux 9 guest
```

Preserve the existing Go control plane and current Ansible roles/playbooks. Work only the current provider's first unmet gate.

For disposable acceptance cleanup, manually recreated/reinstalled Rocky VMs are preferred over building lab-only reimage automation. Product idempotency/repair/upgrade/uninstall/backup/restore requirements remain mandatory.

## 6. DC/DR contract

Use native CloudStack first:

```text
healthy DC/DR infrastructure
 -> native B&R enabled/configured
 -> Recovery Point OLD
 -> mutate data
 -> Recovery Point NEW
 -> selected createVMFromBackup recovery
 -> isolated destination network
 -> exact OLD/NEW root/data verification
 -> retry/RBAC/negative cases
 -> thin LayerSentry orchestration
```

Only after native recovery passes should one selected provider-native low-RPO path required by V1 be implemented/qualified. Planned failover/failback precedes witness/fencing/automatic failover.

## 7. UI and release activation

UI remains dormant while backend contracts are moving. Run one bounded final pass when real VM/K8s/Data Services/DR contracts are stable enough for integration and browser acceptance.

Release/signing/security work is not a standing stream. Activate it only when an exact artifact is ready for promotion or a concrete trust/security defect blocks a vertical slice.

One logical V1 carrier remains `layersentry-platform-<release>.iso`; bundled packages are `AVAILABLE`, not automatically installed.

## 8. Status maintenance

Module writers update their **module-specific status/evidence** after meaningful evidence milestones.

`LAYERSENTRY_CURRENT_STATUS.md` is refreshed by an integration/status/governance pass when any module's status, first unmet gate or authoritative pointer materially changes. Keep it compact; do not copy historical logs into it.

`LAYERSENTRY_PROGRESS_LEDGER.md` remains historical/audit evidence and is read only when older history is needed.

## 9. Completion/stop rules

For any module:

1. work only the first unmet gate;
2. stop adding features while that gate fails;
3. fix the smallest correct owner inside the file fence;
4. rerun the same gate;
5. persist only meaningful evidence milestones;
6. stop when the next required change is foreign-module, needs a manual lab reset or requires unavailable infrastructure/resources.

Progress is measured by customer-operable vertical slices, not commits, lines or document volume.

## 10. Conflict rule

This contract supersedes older execution-routing, startup-read-order and sequencing instructions where they conflict. Detailed specialist storage/network/security/data-safety architecture remains valid unless explicitly superseded.
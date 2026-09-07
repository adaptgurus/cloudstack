# LayerSentry V1 — Execution Contract

**Contract schema:** 1.5  
**Effective date:** 2026-09-08  
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

### 2.1 Low-credit execution budget

Use the smallest working set capable of resolving the first unmet gate:

```text
current status + exact ref
 -> first unmet gate
 -> changed/relevant paths only
 -> focused source/static/unit validation
 -> focused module CI/integration validation
 -> required live/destructive E2E gate
 -> compact evidence/status update
```

Rules:

1. Do not rescan the whole repository during continuation work unless explicitly assigned a repository-level audit or new evidence shows the ownership boundary is wrong.
2. Do not reload large unchanged masters/workstreams/logs in one session; use exact sections, diffs, search results and evidence pointers.
3. Do not create new recap/master/handoff documents for normal progress. Update existing module status/evidence only when a material milestone changes.
4. After one confirmatory rerun, the same expensive failing workflow/lab action requires changed code/config/artifact/environment or a changed diagnostic hypothesis before another retry.
5. Prefer one focused failing test/job while diagnosing; run the broader required suite after the focused defect is fixed or when the release gate itself requires it.
6. Never run parallel source writers on the same module/gate. Test/read-only parallelism must have a specific question and must not independently design competing fixes.
7. Do not implement speculative fallback architecture while the selected lifecycle still has an evidence-driven next gate. Invoke fallback only through the formal stop-loss decision.
8. Persist hashes, run/job IDs, exact failure signatures and short conclusions; keep bulk logs/artifacts out of mandatory startup context.
9. If an external/manual blocker is reached, stop and record the exact prerequisite instead of generating code that cannot be validated.
10. Credit efficiency never permits skipping required security, integration, destructive, upgrade, restore or production-certification evidence.

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

One lifecycle serves user Kubernetes, Kubernetes-backed DBaaS, APaaS and Streaming:

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

### Current K8s scope exclusions

Workstream E does **not** own or implement:

- VM-native Single-OS DBaaS/APaaS;
- cross-site RKE2 application DR;
- Kubernetes-backed DBaaS DC->DR replication/promotion;
- APaaS cross-site DR;
- RKE2 failover/failback, RPO/RTO or cross-site DNS/VIP switching;
- RKE2 DR UI.

Those items must not become K8s completion blockers unless the owner explicitly reopens that scope. The independent DC/DR workstream continues separately.

CSI/PVC project isolation, resize, stateful Machine replacement and data survival remain in scope because they are core stateful Kubernetes safety properties, not cross-site DR.

DB backup/restore/PITR remain in scope only when those Day-2 DBaaS capabilities are advertised.

The customer-facing UI/API may normalize lifecycle and operation status across modules, but implementation must reuse existing LayerSentry journal/reconciliation and underlying lifecycle owners. Do not add another generic service-control engine merely to wrap CAPI, CloudStack, Flux or upstream operators.

### CAPC stop-loss

If a bounded qualification campaign repeatedly cannot achieve CloudStack VM creation + automatic RKE2 join + 6443/9345 + `Ready`, and evidence shows continued CAPC maintenance is disproportionate, record a release decision and assign the approved fallback:

```text
native CloudStack APIs -> QCOW2/cloud-init -> Ansible Runner -> RKE2 -> Flux
```

One release uses one cluster lifecycle owner.

### Upstream services

Use pinned/qualified OpenEverest, OpenBao, Harbor and Strimzi. LayerSentry integration is limited to Flux/Helm/artifacts, namespace/RBAC, storage/network/VIP policy, status/audit and E2E qualification. Do not rewrite their operators/controllers, backup/PITR engines or UIs.

A service does not advance because its package/UI exists. Advance only after the applicable vertical slice proves authorization, create/ready, durable status/reconciliation and required Day-2/data-safety gates.

## 5. VM-native Single-OS contract

Architecture:

```text
LayerSentry UI/API -> Go orchestration -> Ansible Runner -> Rocky Linux 9 guest
```

Preserve the existing Go control plane and current Ansible roles/playbooks. Work only the current provider's first unmet gate.

For disposable acceptance cleanup, manually recreated/reinstalled Rocky VMs are preferred over building lab-only reimage automation. Product idempotency/repair/upgrade/uninstall/backup/restore requirements remain mandatory.

## 6. Independent DC/DR contract

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

This workstream is independent from the current RKE2 application/Data Services scope; do not infer RKE2 application DR requirements from it.

## 7. UI and release activation

UI remains dormant while backend contracts are moving. Run one bounded final pass when real VM/K8s/Data Services/independent DR contracts are stable enough for integration and browser acceptance.

The final pass consumes stable backend contracts and common customer-facing lifecycle/operation vocabulary rather than inventing module-specific status semantics in the frontend.

Release/signing/security work is not a standing stream. Activate it only when an exact artifact is ready for promotion or a concrete trust/security defect blocks a vertical slice.

One logical V1 carrier remains `layersentry-platform-<release>.iso`; bundled packages are `AVAILABLE`, not automatically installed.

## 8. Status maintenance

Module writers update their module-specific status/evidence after meaningful evidence milestones.

`LAYERSENTRY_CURRENT_STATUS.md` is refreshed by an integration/status/governance pass when a module status, first unmet gate or authoritative pointer materially changes. Keep it compact; do not copy historical logs into it.

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
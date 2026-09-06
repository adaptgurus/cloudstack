# Codex Workstream E — LayerSentry K8s / DBaaS / APaaS / Streaming

## Mission

Implement the LayerSentry-managed Kubernetes, DBaaS, APaaS and Streaming module defined by `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` while preserving Apache CloudStack 4.22.1.1 core semantics and all unrelated LayerSentry V1 modules.

This workstream owns only the new Kubernetes/Data Services/APaaS/Streaming product surface and its LayerSentry-specific integration code. It must not refactor VM Quick Provision, DR, CloudStack management HA, object storage, release signing, appliance lockdown or unrelated UI simply because those components are nearby.

## Startup

Read, in order:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`
5. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md`
6. latest applicable dated validation under `docs/layersentry/evidence/k8s/` — currently `2026-09-06-k8s-master-context-full-validation.md`
7. this file
8. relevant specialist security/release/debugging policy only when the task needs it.

Fetch the actual current branch/commit and inspect current source before editing. Work in an isolated worktree/branch.

The dated validation file contains volatile exact-version/source findings. Revalidate them before changing the release tuple; do not treat a dated version as permanent merely because it is recorded there.

## Core architecture that must not drift without a new research decision

```text
LayerSentry UI/API
  -> CAPI
     -> CAPC -> CloudStack 4.22.1.1/KVM
     -> CAPRKE2 -> RKE2
  -> central Flux -> selected packages on remote CAPI clusters
  -> CloudStack native APIs for discovery/IP/network/storage/platform operations outside CAPC Machine ownership
```

Rules:

- CAPC owns CAPI Machine infrastructure; do not independently delete/mutate those VMs behind CAPC.
- CAPRKE2 owns automatic RKE2 join/bootstrap/control-plane lifecycle.
- CloudStack remains the KVM/IaaS authority.
- CloudStack CCM owns supported Kubernetes L4 LoadBalancer reconciliation where selected.
- Gateway API owns L7 intent.
- certified OEM controllers own hardware ADC/WAF state.
- Flux owns LayerSentry internal package reconciliation.
- database/application operators own their application lifecycle.
- no manual RKE2 join in normal managed-cluster flows.
- one controller owns each VIP, VM, node disk, CSI volume and application lifecycle.

## Current E0 compatibility decision

Do not begin implementation by assuming the newest tag of every provider is mutually compatible.

The 2026-09-06 source audit established three lanes:

### Lane A — released legacy overlap

```text
CAPI       1.9.6
CAPC       0.6.1
CAPRKE2    0.15.0
Kubernetes workload support ceiling from CAPI 1.9 matrix: 1.32
```

This is useful evidence that a released overlap exists but it is **not** the intended LayerSentry current production lane because the target is Kubernetes/RKE2 1.36.x.

### Lane B — first modern released-artifact qualification candidate

```text
CloudStack 4.22.1.1
CAPI       1.13.5
CAPRKE2    0.25.2
CAPC       0.6.1
RKE2       1.36.4+rke2r1 candidate
```

CAPI v1beta2 currently offers temporary backward compatibility with v1beta1 infrastructure providers, so CAPC 0.6.1 is **not automatically incompatible** with CAPI 1.13.5/CAPRKE2 0.25.2. This is a bridge to test, not a production support statement.

Test Lane B first because CAPC and CAPRKE2 are released artifacts.

### Lane C — modern CAPC contract candidate

Use a reviewed/pinned CAPC build from upstream PR `#493` or a later released equivalent implementing the CAPI v1beta2 infrastructure contract.

PR #493 was open/unmerged during the validation. Never call it an upstream stable release. If used, record exact commit/digest/delta and qualify it like a LayerSentry downstream component.

### Selection rule

No production tuple is selected until E0 evidence compares the applicable lanes and passes the lifecycle/data-safety matrix. The final tuple goes in the LayerSentry release manifest/evidence, not hard-coded throughout application source.

## Hard E0 release blockers discovered by source validation

### 1. RKE2 endpoint 9345

CAPRKE2 joins nodes through RKE2 registration/supervisor TCP `9345`. Current CAPC isolated-network endpoint code creates the CloudStack Kubernetes API LB rule for `6443` and does not by itself prove a second RKE2 rule exists.

LayerSentry must provide one owned HA endpoint with at least:

```text
VIP/FQDN:6443 -> RKE2 servers:6443
VIP/FQDN:9345 -> RKE2 servers:9345
```

Prefer a minimal CAPC endpoint enhancement or another explicitly owned/qualified endpoint provider. Do not split one VIP across two hidden controllers without lifecycle ownership.

### 2. CAPC DATADISK deletion/data-loss risk

Current CAPC source still lists all attached `DATADISK` volumes and passes the IDs into VM destruction. Therefore a CSI workload volume attached to a Machine can be at risk during Machine deletion/rollout/scale-down unless ownership is fixed.

Before any stateful production profile:

- distinguish CAPC-owned node disk(s) from CSI/unowned volumes;
- delete only Machine-owned volumes;
- prove workload PVC survives Machine delete/replacement/remediation with data intact.

Until then:

- stateful MachineHealthCheck remediation is disabled;
- DB worker automatic scale-down is disabled;
- DBaaS production certification is blocked.

### 3. Multiple direct node disks

Current CAPC models one deploy-time `DiskOffering`, not an arbitrary list of extra worker disks.

Multiple Kubernetes PVCs/StorageProfiles are valid. Multiple direct CloudStack node disks require a LayerSentry/CAPC `NodeDiskSet`-style ownership contract with volume IDs, tags, purpose and retain/delete/resize/replacement semantics.

Do not expose arbitrary multiple node disks as production-ready until this is implemented and tested. Durable DB/application data remains CSI/PVC-based.

### 4. CloudStack CSI resize

CloudStack CSI `3.0.2` adds default project scoping and may fix part of the earlier project lookup failure, but project-scoped expansion and idempotency must still be tested on CloudStack 4.22.1.1 before auto-grow is certified.

### 5. Full air-gap

No upstream component's marketing claim is sufficient. Deny all external egress and prove create/scale/repair/replace/package/backup/restore/upgrade for the exact release.

## Primary implementation areas

Exact paths may be created/refined during design review, but keep LayerSentry-specific source isolated wherever practical.

Expected ownership includes:

- LayerSentry K8s/DBaaS/APaaS/Streaming UI modules and tests;
- LayerSentry API/BFF/controller code for these modules;
- CAPI/CAPC/CAPRKE2 profile/templates/compatibility definitions;
- Flux package definitions and package catalog metadata;
- StorageProfile/StorageHostProfile integration definitions;
- NodeDiskSet/node-disk ownership definitions when direct worker disks are implemented;
- Frontend/VIP/Gateway/WAF provider abstraction;
- offline K8s/Data Services bundle manifests/build definitions in coordination with Workstream B;
- OpenEverest branding overlay/build integration;
- Redis/Valkey provider integration;
- Strimzi/Kafka package integration;
- OpenBao/Harbor package integration;
- module-specific E2E/negative/failure/upgrade tests.

Do not modify CloudStack Java/backend/database/KVM core unless the integration lead approves a documented core-change exception.

## Required delivery order

Do not start by wiring every optional package.

### E0 — compatibility, endpoint and data-safety audit

- revalidate exact CAPI/CAPC/CAPRKE2/RKE2 tuple;
- test Lane B first and compare Lane C when needed;
- inspect CAPC compatibility/issues against CloudStack 4.22.1.1;
- prove/implement 6443 + 9345 RKE2 HA endpoint ownership;
- fix and test CAPC Machine deletion so CSI/unowned DATADISK volumes cannot be destroyed;
- define NodeDiskSet ownership before exposing multiple direct node disks;
- inspect CloudStack CCM/CSI exact release behavior/issues;
- define release/compatibility schema;
- preserve all uncertainty as explicit gates.

E0 is not complete while the 9345 endpoint or CAPC attached-volume deletion problem is unresolved.

### E1 — base LayerSentry K8s vertical slice

- management-cluster assumptions/installer contract;
- CAPI cluster creation;
- CAPC CloudStack infrastructure;
- CAPRKE2 automatic RKE2 bootstrap/join;
- one primary CNI;
- CloudStack CCM;
- one safe storage path;
- central Flux;
- GUI create/status/delete/scale flow;
- exact offline artifact set.

Do not introduce stateful DBaaS until E0 volume survival is proven.

### E2 — storage/network profiles

- multiple StorageProfiles per cluster;
- CloudStack node data disks only after NodeDiskSet/ownership certification;
- CloudStack CSI after safety qualification;
- CloudStack SharedFS/NFS + NFS CSI;
- first OEM CSI;
- Frontend/VIP abstraction;
- CloudStack L4 exposure;
- first Gateway API L7 provider;
- hardware ADC/WAF adapter contract.

### E3 — DBaaS

- dedicated Data Services ClusterClass/profile;
- 3 control plane + 4 DB worker production profile;
- NVMe-only DB storage policy;
- OpenEverest stable provider with LayerSentry branding persistence;
- PostgreSQL first vertical slice;
- MySQL/MongoDB after PostgreSQL proof;
- Redis/Valkey adapter;
- backup/PITR/monitoring/maintenance UI.

OpenEverest current stable support must be revalidated. Versioned v1.16.2 documentation supports Kubernetes 1.33-1.36 and explicitly does not support air-gapped environments upstream, so any offline profile is LayerSentry-engineered and must pass deny-all-egress testing.

### E4 — APaaS / Streaming

- OpenBao HA profile;
- Harbor HA profile without bootstrap-registry circular dependency;
- Strimzi/Kafka with protocol-correct multi-VIP exposure where selected.

### E5 — GPU/advanced storage

- GPU worker pool and GPU QCOW2;
- NVIDIA offline artifacts/license handling;
- NVMe/TCP certification;
- NVMe/RDMA only after exact hardware/KVM/SR-IOV/OEM qualification;
- no GPUDirect claim without exact certification.

## GUI rule

Normal users operate only through LayerSentry GUI/API workflows.

Do not require users to edit YAML, run `kubectl`, SSH nodes, enter RKE2 join tokens, manage raw IQNs/LUNs or understand CRDs/Helm releases for normal provisioning.

Advanced/Support views may expose low-level evidence to authorized roles.

## Storage rule

A cluster may use several StorageProfiles at once.

Never confuse:

- CloudStack shared primary storage;
- one CloudStack data volume;
- CloudStack Shared FileSystem/NFS;
- Kubernetes CSI block;
- OEM shared file/block capabilities.

General RWX shared storage uses CloudStack SharedFS/NFS or a certified OEM file solution. Do not attach one ordinary raw block volume read-write to all nodes unless an exact certified multi-writer storage/filesystem design proves it safe.

Host utilities such as `lsscsi`, iSCSI, multipath, NVMe and NFS may be preinstalled in the QCOW2. Unselected CSI controllers are not installed into the cluster.

Direct node disks are a separate Machine/node-pool lifecycle. They must never be confused with CSI workload volumes, and deletion must be ownership/tag driven.

## VIP/network rule

One externally managed VIP equals one LayerSentry Frontend lifecycle object. One backend may have multiple Frontends/VIPs. One shared L7 Gateway VIP may serve many hostnames when policy permits.

CloudStack native load balancing is treated as L4. Gateway API/controller handles L7. Hardware ADC/WAF integrations use their supported Kubernetes/API integration and do not require a CloudStack core patch.

DB protocols default to private L4. Kafka uses the listener/VIP model required by the exact Strimzi configuration.

RKE2 cluster control-plane VIP is separate from application VIPs and must own/reconcile all required control-plane ports, including 6443 and 9345 for the validated CAPRKE2/RKE2 line.

## Package rule

`AVAILABLE` does not mean installed.

Users can install packages later without reinstalling the ISO. Central Flux reconciles selected package versions to the remote cluster. If a new package needs a host driver/kernel change, surface the required CAPI node-image rollout before installation.

## OpenEverest branding rule

LayerSentry branding must survive upgrades.

Prefer a LayerSentry-owned DBaaS UI/API facade long term. Early releases may use a pinned LayerSentry OpenEverest image built from an exact upstream tag plus automated branding overlay. Build must fail if the overlay cannot be applied or forbidden customer-facing upstream branding returns.

Do not remove required open-source attribution.

## Alternative-platform decision rule

Do not reopen the core architecture casually.

- Cozystack: use package/OCI/Flux ideas; do not add a second cloud/IaaS authority.
- Otomi/Akamai App Platform: UX/platform reference, not mandatory control plane.
- KubeBlocks: architectural reference; current repository AGPL-3.0 code is not embedded without legal approval.
- KubeDB Platform: keep as an explicit commercial/OEM DBaaS alternative if broader engine/offline/white-label time-to-market outweighs open-source ownership.
- Rancher/Turtles: not mandatory in V1; adding it must show measurable benefit and does not eliminate CAPC qualification.

## Anti-hallucination / production gate

Never mark a combination supported because an API/field/name appears to imply the behavior.

For every major integration:

1. exact release source/docs;
2. issues/PRs/community failure history;
3. LayerSentry compatibility decision;
4. source/CI tests;
5. live E2E tests on the designated acceptance environment;
6. destructive failure/data/upgrade tests where applicable;
7. only then the appropriate status promotion.

Specific release blockers include CAPC Machine/PVC data safety, RKE2 9345 endpoint ownership, CloudStack CSI project-scoped resize/idempotency, safe direct-node-disk lifecycle, complete air-gap operation, node replacement, VIP reconciliation and DB data integrity.

## Coordination with other workstreams

- **A UI/Self-Service:** shared design system, role navigation, existing common components. E owns service-specific K8s/DBaaS/APaaS behavior; coordinate rather than duplicate.
- **B Release/Installer:** B owns signing/SBOM/provenance/update mechanics. E defines K8s/Data Services artifact requirements.
- **C Security/Validation:** C owns shared RBAC/security/evidence framework; E adds module-specific cases.
- **D DR/HA/Upgrade:** D owns global DR/HA/upgrade proof framework; E supplies Kubernetes/Data Services workload-specific hooks/evidence. Do not create a second DR system.

## Handoff

Every handoff reports:

- repository/branch/base/final commit;
- exact module scope;
- files changed;
- CloudStack-core impact YES/NO;
- architecture/version tuple researched;
- checks actually run;
- runtime mutations/evidence;
- known limitations/blockers;
- upgrade/rollback/recovery state;
- next production gate.

Do not edit unrelated contexts to claim progress. Update the shared progress ledger only when assigned/integration lead and only with actual evidence.

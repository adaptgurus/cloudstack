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
5. this file
6. relevant specialist security/release/debugging policy only when the task needs it.

Fetch the actual current branch/commit and inspect current source before editing. Work in an isolated worktree/branch.

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

## Primary implementation areas

Exact paths may be created/refined during design review, but keep LayerSentry-specific source isolated wherever practical.

Expected ownership includes:

- LayerSentry K8s/DBaaS/APaaS/Streaming UI modules and tests;
- LayerSentry API/BFF/controller code for these modules;
- CAPI/CAPC/CAPRKE2 profile/templates/compatibility definitions;
- Flux package definitions and package catalog metadata;
- StorageProfile/StorageHostProfile integration definitions;
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

### E0 — compatibility and source audit

- pin/research exact CAPI/CAPC/CAPRKE2/RKE2 tuple;
- inspect CAPC compatibility/issues against CloudStack 4.22.1.1;
- inspect CloudStack CCM/CSI behavior/issues;
- define release/compatibility schema;
- preserve all uncertainty as explicit gates.

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

### E2 — storage/network profiles

- multiple StorageProfiles per cluster;
- CloudStack node data disks;
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

## VIP/network rule

One externally managed VIP equals one LayerSentry Frontend lifecycle object. One backend may have multiple Frontends/VIPs. One shared L7 Gateway VIP may serve many hostnames when policy permits.

CloudStack native load balancing is treated as L4. Gateway API/controller handles L7. Hardware ADC/WAF integrations use their supported Kubernetes/API integration and do not require a CloudStack core patch.

DB protocols default to private L4. Kafka uses the listener/VIP model required by the exact Strimzi configuration.

## Package rule

`AVAILABLE` does not mean installed.

Users can install packages later without reinstalling the ISO. Central Flux reconciles selected package versions to the remote cluster. If a new package needs a host driver/kernel change, surface the required CAPI node-image rollout before installation.

## OpenEverest branding rule

LayerSentry branding must survive upgrades.

Prefer a LayerSentry-owned DBaaS UI/API facade long term. Early releases may use a pinned LayerSentry OpenEverest image built from an exact upstream tag plus automated branding overlay. Build must fail if the overlay cannot be applied or forbidden customer-facing upstream branding returns.

Do not remove required open-source attribution.

## Anti-hallucination / production gate

Never mark a combination supported because an API/field/name appears to imply the behavior.

For every major integration:

1. exact source/docs;
2. issues/PRs/community failure history;
3. LayerSentry compatibility decision;
4. source/CI tests;
5. live E2E tests on the designated acceptance environment;
6. destructive failure/data/upgrade tests where applicable;
7. only then the appropriate status promotion.

Specific release blockers include CAPC Machine/PVC data safety, CloudStack CSI project-scoped operations/resize, complete air-gap operation, node replacement, VIP reconciliation and DB data integrity.

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

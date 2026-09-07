# Codex Workstream E — LayerSentry RKE2 / Kubernetes / Data Services

**Execution owner:** Codex  
**Primary objective:** finish one reusable LayerSentry RKE2 lifecycle end to end, then install/qualify upstream services through the same Flux package plane  
**Cloud baseline:** Apache CloudStack 4.22.1.1 + KVM  
**Customer Kubernetes distribution:** RKE2

This is the primary technical Codex workstream. Workstream A is the separate bounded Codex UI-finishing stream. Do not spend this workstream on VM-native Single-OS implementation or native DR troubleshooting.

## 1. Minimal startup

Read only:

1. `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
5. this file;
6. fetch the actual integration branch, current `release-candidate-lane-b.json`, workflow state and live target.

Open dated evidence only for the exact blocker/version being worked. Do not reread every historical K8s audit.

## 2. Current architecture — one cluster lifecycle

Preferred path:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack 4.22.1.1/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> central Flux
 -> selected packages/operators
```

One lifecycle serves:

- user/self-service RKE2;
- Data Services RKE2 profiles;
- APaaS profiles;
- Streaming/Kafka profiles.

Profiles differ in node pools, placement, storage, networking, security and package selection. They do **not** receive separate cluster provisioning engines.

Ownership:

- CloudStack owns IaaS, project/account/RBAC/quota and native infrastructure state;
- CAPI owns cluster/machine desired state;
- CAPC owns CloudStack resources created for CAPI Machines;
- CAPRKE2 owns RKE2 bootstrap/control-plane lifecycle;
- CloudStack CCM owns the selected Kubernetes L4 LoadBalancer lifecycle;
- CSI owns workload-volume lifecycle on the certified storage path;
- Flux owns internal package reconciliation;
- upstream DB/application operators own application-specific lifecycle;
- LayerSentry owns UI/BFF, profiles, compatibility, policy, audit, entitlement and composite workflow state.

Never create two active controllers for one VM, VIP, node disk, CSI volume, cluster or application lifecycle.

## 3. Existing source must be reused

The integration branch already contains substantial source for:

- BFF/auth/RBAC;
- durable saga/journal/reconciliation;
- CloudStack API client/preflight;
- CAPI/CAPC/CAPRKE2 resource generation;
- create/status/scale/delete executor;
- CAPC dual 6443/9345 endpoint and volume-ownership work;
- CloudStack CCM Kubernetes 1.36 downstream work;
- CloudStack CSI idempotent/project qualification work;
- NodeDiskSet planning;
- Flux resources;
- systemd/runtime wiring;
- K8s/Data Services UI source and tests.

Do not rebuild these foundations or add adjacent frameworks merely to increase code percentage.

## 4. First objective: close E0/E1 live gates

The current release candidate remains blocked until the hard gates in `tools/layersentry/k8s/release-candidate-lane-b.json` pass.

### 4.1 Immutable artifacts

Resolve and publish exact immutable artifacts required by the release candidate:

- CAPC/downstream build when applicable;
- CAPRKE2;
- RKE2 artifacts;
- CloudStack CCM final image;
- patched CloudStack CSI final image;
- selected CNI;
- Flux components/catalog;
- LayerSentry controller/BFF package;
- OS/QCOW2 image;
- required SBOM/provenance/digests/signatures.

Do not deploy stable candidates from moving tags, unresolved package repositories or null final images.

### 4.2 Controller deployment

Deploy the exact controller/BFF/reconciler stack and prove:

- service start/restart;
- CloudStack session/auth/RBAC integration;
- CloudStack API connectivity;
- Kubernetes management API connectivity;
- durable reconciliation after restart;
- no secret leakage;
- fail-closed unresolved component behavior.

### 4.3 One real cluster create

From the LayerSentry GUI/API:

```text
select project/Site/network/offering/template/profile
 -> create CAPI objects
 -> CAPC creates CloudStack VMs/resources
 -> CAPRKE2 automatically bootstraps/joins nodes
 -> 6443 reachable
 -> 9345 reachable
 -> control plane forms
 -> workers join
 -> cluster Ready
```

No user-pasted token, manual SSH or manual YAML is part of the normal managed workflow.

### 4.4 Networking

Prove one primary CNI first. Do not qualify every CNI simultaneously.

Then prove CloudStack CCM/L4 on the exact release:

- `Service type=LoadBalancer` create;
- backend readiness/membership;
- update/reconcile;
- delete/cleanup;
- controller restart/recovery.

### 4.5 Storage/data safety

Prove one production-safe CSI/storage path first:

- project scoping/isolation;
- provision/attach/mount/detach/delete;
- snapshot/restore where supported;
- resize/idempotency where offered;
- worker/Machine replacement;
- CAPC Machine deletion does **not** destroy unowned CSI workload data;
- NodeDiskSet ownership explicit where exposed;
- ambiguous mutation is observed/reconciled before retry.

Stateful service profiles remain blocked until these gates pass.

### 4.6 Flux

Prove central Flux from immutable content:

- exact source/digest;
- remote cluster reconciliation;
- HelmRelease/package install;
- update/remove;
- controller restart/recovery;
- no Internet dependency for an offline-certified release.

This package plane is reused by OpenEverest, OpenBao, Harbor, Strimzi and other approved services.

### 4.7 Day-2

Prove:

- status;
- scale up;
- safe scale down where data ownership permits;
- worker replacement;
- control-plane replacement where supported;
- restart/reconciliation;
- delete/cleanup;
- timeout/UNKNOWN recovery;
- exact supported RKE2/Kubernetes upgrade path.

## 5. E2E-first defect loop

For each live failure:

1. capture exact failure, resource/job IDs and logs;
2. classify owner: CloudStack, environment, CAPC, CAPRKE2, RKE2, CNI, CCM, CSI, Flux or LayerSentry;
3. fix the **smallest correct owner**;
4. add regression coverage;
5. build the affected immutable artifact;
6. redeploy the exact artifact;
7. rerun the same step;
8. continue only after it passes.

Do not redesign the architecture for a fixable integration defect.

## 6. CAPC/CAPRKE2 stop-loss

CAPI/CAPC/CAPRKE2 remains preferred because substantial source and downstream work already exists.

Do not patch CAPC indefinitely.

If a bounded focused qualification campaign repeatedly cannot reach all four minimum base outcomes:

1. CloudStack VMs/resources created correctly;
2. CAPRKE2 automatic join works;
3. 6443 and 9345 are reachable/owned correctly;
4. cluster reaches `Ready`;

and evidence shows the remaining downstream maintenance is disproportionate, record a release decision and switch to:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

Rules:

- one release, one lifecycle owner;
- do not maintain both paths as active alternatives for the same release;
- fallback installation/configuration uses Ansible, not shell lifecycle;
- CloudStack remains IaaS authority;
- reuse the same CNI/CCM/CSI/Flux/package contracts above the fallback cluster.

## 7. Upstream service integration — do not rebuild products

After the base RKE2/CSI/CCM/Flux lifecycle is live-proven, the remaining service work is primarily **pinned manifest/Helm integration and E2E qualification**.

### 7.1 OpenEverest

For supported PostgreSQL/PXC-MySQL/MongoDB V1 services, use the exact qualified **OpenEverest stable v1 line** and its existing database operators/control-plane semantics.

Codex SHALL NOT implement a replacement:

- PostgreSQL/MySQL/MongoDB operator;
- DB HA/failover controller;
- database backup scheduler;
- PITR engine;
- database engine-upgrade controller;
- replacement DBaaS frontend merely to duplicate OpenEverest.

LayerSentry work is limited to the necessary integration:

```text
Flux source/HelmRelease
 -> namespace/RBAC/project policy
 -> certified StorageClass
 -> network/VIP/exposure policy
 -> local/offline artifact references
 -> health/status integration
 -> E2E qualification of the upstream lifecycle
```

For current V1, do not spend Codex work rebranding the OpenEverest UI unless the owner explicitly assigns branding later.

Certification may still require proving one supported database lifecycle through OpenEverest: create, read/write, HA/failure behavior, backup, PITR/restore where offered, upgrade, worker replacement/data integrity and delete/retention. Those are **tests of upstream integration**, not a mandate to rewrite the features.

### 7.2 OpenBao

Install from pinned supported Helm/OCI content through Flux. Configure the certified HA/storage/network/TLS values and test required failure/backup/upgrade behavior. Do not write an OpenBao controller.

### 7.3 Harbor

Install from pinned supported Helm/OCI content through Flux. Configure certified persistence, external/HA dependencies, network exposure and scanning/signing integrations as selected. Do not write a Harbor controller.

### 7.4 Strimzi/Kafka

Install the pinned Strimzi operator through Flux and use Strimzi CRs for Kafka lifecycle. LayerSentry provides profile inputs and networking/storage policy. Do not write a Kafka operator.

Kafka external exposure may require bootstrap plus broker-specific endpoints; validate this exact listener/VIP behavior rather than assuming one generic VIP.

### 7.5 Additional services

Use a mature existing operator/provider where one exists. Do not create custom operators solely to enlarge the catalog.

## 8. One signed V1 platform carrier

Current V1 execution uses one logical signed release carrier:

```text
layersentry-platform-<release>.iso
```

It can contain logical sections for:

- QCOW2/RKE2/CAPI/CAPC/CAPRKE2;
- CNI/CCM/CSI;
- Flux;
- OpenEverest/database operators/images;
- OpenBao;
- Harbor;
- Strimzi/Kafka;
- approved security/observability/backup packages;
- local RPM/DEB/OCI/chart content;
- compatibility manifest, signatures, checksums, SBOM and provenance.

Bundled means `AVAILABLE`. Flux installs only selected packages. Package installation later must not require reinstalling the ISO or rebuilding the cluster unless a host/kernel dependency changes.

This current V1 decision supersedes the older conceptual split into separate K8s and Data Services ISO carriers for execution.

## 9. UI coordination

General LayerSentry UI finishing is Codex Workstream A. Workstream E owns K8s-specific API contract and integration requirements.

Coordinate shared files such as router/config/API contracts before edits. Do not duplicate lifecycle logic in Vue/browser code.

For K8s/Data Services, UI must truthfully expose only real capabilities and provide:

- create/status/scale/delete;
- profile/release selection;
- storage/network/VIP choices;
- package/service selection;
- meaningful progress/errors;
- RBAC/direct-route correctness.

No broad UI redesign belongs in Workstream E.

## 10. Air-gap

Air-gap is proven only by denying external egress and completing the claimed lifecycle from local pinned artifacts.

For the stable profile test, as applicable:

- cluster create;
- scale;
- replacement/repair;
- Flux package install/update;
- one OpenEverest service lifecycle;
- backup/restore where claimed;
- upgrade/rollback.

An upstream project saying it does or does not support air-gap is not LayerSentry runtime proof. If LayerSentry mirrors all required artifacts and qualifies the result, record it as a LayerSentry-certified profile, not as an inherited upstream claim.

## 11. Testing minimum

For the exact release include, as applicable:

- existing source/unit tests;
- exact component builds;
- immutable artifact validation;
- controller restart/recovery;
- auth/RBAC/project negatives;
- cluster create/status/scale/delete;
- 6443/9345;
- CNI/CCM/CSI lifecycle;
- PVC survival under node replacement;
- Flux package lifecycle;
- selected upstream service lifecycle;
- upgrade/rollback;
- air-gap;
- browser E2E through Workstream A;
- Rocky Linux 9 runtime evidence;
- timeout/ambiguous-mutation reconciliation.

Do not promote mocks/source tests to `LIVE_VERIFIED`.

## 12. Codex efficiency rules

- stay on the first failing vertical gate until resolved;
- reuse existing source instead of starting a replacement controller;
- do not implement upstream product features that already exist;
- do not build separate cluster engines for DBaaS/APaaS/Streaming;
- do not qualify every CNI/CSI/provider simultaneously;
- do not repeatedly research frozen versions without a blocker;
- keep one active K8s Codex implementation stream unless the owner explicitly authorizes a non-overlapping substream;
- checkpoint only meaningful milestones, not every tiny edit.

## 13. Handoff

Report concisely:

- exact branch/base/final commit;
- exact release tuple/artifact digests;
- first/last vertical step reached;
- tests/live actions actually executed;
- exact observed failure/root cause if blocked;
- storage/data-safety result;
- fallback decision if any;
- exact next failing gate.

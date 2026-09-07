# Codex Workstream E — LayerSentry RKE2 / Kubernetes / DBaaS / APaaS / Streaming

**Execution owner:** Codex  
**Primary objective:** convert existing source foundations into working end-to-end vertical slices  
**Cloud baseline:** Apache CloudStack 4.22.1.1 + KVM  
**Customer distribution:** RKE2

This is the primary Codex workstream. Do not spend Codex capacity on UI redesign, VM-native Single-OS providers or native DR troubleshooting unless the owner explicitly reassigns scope.

## 1. Startup

Read only:

1. `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
5. this file;
6. fetch actual branch/current component/runtime state.

Open dated validation/evidence only for the exact blocker/version being worked. Do not reread every historical K8s audit by default.

## 2. Frozen architecture unless evidence invalidates it

Preferred path:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack 4.22.1.1/KVM
    -> CAPRKE2 -> RKE2
 -> central Flux
 -> CNI/CCM/CSI/operators
```

Ownership rules:

- CloudStack owns IaaS and account/project/RBAC/quota;
- CAPI owns cluster/machine desired state;
- CAPC owns CloudStack resources created for CAPI Machines;
- CAPRKE2 owns RKE2 bootstrap/control-plane lifecycle;
- CloudStack CCM owns selected Kubernetes L4 load-balancer lifecycle;
- Flux owns internal package reconciliation;
- CSI owns workload-volume lifecycle on its certified path;
- database/application operators own application-specific lifecycle;
- LayerSentry owns GUI, policy, compatibility, audit and composite workflow state.

Never create two active controllers for one VM, VIP, node disk, CSI volume or application lifecycle.

## 3. Stop broad horizontal scaffolding

The branch already contains substantial source for:

- BFF/auth/RBAC;
- durable saga/journal/reconciliation;
- CloudStack client/preflight;
- CAPI/CAPC/CAPRKE2 resource generation;
- lifecycle executor;
- CAPC downstream endpoint/volume-ownership work;
- CCM Kubernetes 1.36 source overlay;
- CSI idempotent-expansion work;
- NodeDiskSet planning;
- systemd/runtime wiring.

Do not keep adding adjacent frameworks merely to increase code percentage.

The first priority is to publish/deploy the exact components and exercise one complete cluster lifecycle.

## 4. E0/E1 definition of done

Codex must close the existing hard gates through one exact release tuple.

### 4.1 Immutable artifacts

Before deployment, produce/consume exact immutable artifacts for the selected components:

- CAPC/downstream patch/build as applicable;
- CAPRKE2;
- RKE2 release/image artifacts;
- CloudStack CCM;
- patched CloudStack CSI;
- CNI;
- Flux components/catalog;
- controller/BFF package;
- OS/QCOW2 image;
- SBOM/provenance/digests/signatures according to release policy.

No moving tags, unresolved package layers or null final images in a stable candidate.

### 4.2 Management/controller deployment

Deploy the exact controller/BFF/reconciler components on the intended Rocky Linux 9 management environment and prove:

- service start/restart;
- auth/session integration;
- Kubernetes API connectivity;
- CloudStack API connectivity;
- durable reconciliation after process restart;
- no secret leakage;
- fail-closed unresolved component handling.

### 4.3 Cluster create

From LayerSentry GUI/API:

- select project/Site/network/service offering/template/profile;
- create the CAPI cluster;
- CAPC creates the required CloudStack VMs/resources;
- CAPRKE2 performs automatic bootstrap/join;
- user does not paste tokens or SSH nodes;
- 6443 endpoint becomes reachable;
- 9345 supervisor/join endpoint is owned/reconciled and proven;
- cluster reaches Ready.

### 4.4 Networking

Prove one primary CNI first.

Then prove CloudStack CCM/L4 lifecycle on the exact Kubernetes 1.36/RKE2 candidate:

- Service `LoadBalancer` create;
- backend membership/readiness;
- update/reconcile;
- delete/cleanup;
- restart/recovery behavior.

Do not implement every CNI/Gateway/WAF provider before one path works.

### 4.5 Storage/data safety

Prove one safe storage path first.

Hard requirements before stateful DBaaS:

- project scoping/isolation;
- attach/detach;
- snapshot/restore where supported;
- resize/idempotency;
- Machine delete/replacement does not destroy unowned CSI workload data;
- NodeDiskSet/direct node-disk ownership is explicit if that feature is exposed;
- ambiguous mutations reconcile rather than blindly replay.

Stateful DBaaS remains blocked until the exact release passes these gates.

### 4.6 Flux

Prove central Flux from immutable content:

- exact source commit/digest;
- per-cluster reconciliation;
- package install/update/remove;
- controller restart/recovery;
- no dependency on moving Internet content for offline-certified profiles.

### 4.7 Cluster Day-2

Prove:

- status;
- scale up;
- safe scale down only where storage ownership is proven;
- node replacement;
- restart/reconciliation;
- delete/cleanup;
- failure/timeout/unknown-state recovery;
- upgrade path for the exact supported release sequence.

## 5. E2E evidence is the priority

For the current phase, a new code change is valuable only when it closes a concrete E0/E1 gate or an observed E2E defect.

For each failing live step:

1. capture the exact observed failure;
2. identify whether the defect is CloudStack, CAPC, CAPRKE2, RKE2, CCM, CSI, CNI, Flux, LayerSentry or environment;
3. fix the smallest correct owner;
4. add regression coverage;
5. rerun the same vertical step;
6. continue until the full cluster lifecycle passes.

Do not redesign the architecture because of a fixable integration defect.

## 6. Approved fallback

If exact evidence shows CAPC/CAPRKE2 cannot satisfy a required V1 gate without disproportionate downstream maintenance, record a focused decision and select the approved fallback for that release:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

Rules:

- this is a release-level choice, not a second simultaneous owner;
- do not maintain both implementations for one lifecycle;
- fallback RKE2 installation/configuration uses Ansible, not shell-script lifecycle;
- preserve CloudStack as IaaS authority.

## 7. Kubernetes DBaaS sequence

Do not begin broad DB engine coverage until the base RKE2 vertical slice is live-proven.

First Kubernetes DBaaS vertical slice: **PostgreSQL**.

Definition of done includes:

```text
GUI/API provision
 -> dedicated/certified Data Services profile
 -> safe storage
 -> database operator reconcile
 -> service endpoint
 -> health/read-write test
 -> backup
 -> PITR/restore where selected
 -> maintenance/patch/upgrade
 -> restart/node replacement/data integrity
 -> delete/retention behavior
```

Only then expand to MySQL/MongoDB/Redis/Valkey according to the selected provider architecture.

## 8. APaaS/Streaming sequence

After PostgreSQL DBaaS:

1. complete one APaaS vertical slice — OpenBao or Harbor;
2. complete the other only after the first lifecycle is stable;
3. then Strimzi/Kafka with protocol-correct exposure and storage/recovery tests.

Do not build a broad package catalog before proving install/update/recovery semantics.

## 9. Air-gap

Air-gap is proven only by denying external egress and successfully executing the claimed lifecycle using pinned local artifacts.

For a stable offline profile test, as applicable:

- create;
- scale;
- repair/replacement;
- package install/update;
- backup/restore;
- upgrade/rollback.

Marketing/upstream support statements are not proof of the LayerSentry offline combination.

## 10. UI boundary

The broad UI is feature-frozen.

Workstream E changes UI only when required for the K8s/Data Services vertical slice:

- create/status/scale/delete;
- profiles/version selection;
- storage/network/VIP choices;
- package/DBaaS/APaaS status;
- meaningful errors/progress;
- RBAC and direct-route correctness.

Do not launch a general UI redesign from Workstream E.

## 11. Testing minimum

For the exact release, include as applicable:

- source/unit tests;
- exact-component build tests;
- controller service restart/recovery;
- auth/RBAC/project negatives;
- cluster create/status/scale/delete;
- 6443/9345 endpoint tests;
- CNI/CCM/CSI lifecycle;
- storage survival under node replacement;
- package/Flux recovery;
- upgrade/rollback;
- air-gap;
- browser E2E;
- Rocky Linux 9 runtime evidence;
- failure/timeout/ambiguous mutation reconciliation.

Do not promote to `LIVE_VERIFIED` from mocks/source tests.

## 12. Codex token discipline

- remain in this workstream until the current vertical slice is complete;
- do not spend sessions rewriting master contexts unless a material architecture change is required;
- do not duplicate ChatGPT-owned Single-OS/DR/UI work;
- reuse current source instead of rebuilding frameworks from scratch;
- prefer fixing the first failing E2E gate over adding a new provider;
- checkpoint after meaningful vertical milestones, not every tiny edit.

## 13. Handoff

Report concisely:

- exact branch/base/final commit;
- exact release tuple/artifact digests;
- vertical-slice step reached;
- tests/live actions actually executed;
- observed failure/root cause if blocked;
- storage/data-safety result;
- rollback/recovery result;
- exact next failing gate.

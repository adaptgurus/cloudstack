# LayerSentry Kubernetes / DBaaS / APaaS — Super Master Context

**Status:** `DESIGN_DEFINED` until exact source/CI/live evidence promotes a release/profile  
**Role:** stable specialist architecture and production-audit contract  
**Baseline:** Apache CloudStack 4.22.1.1 + KVM  
**Authority:** subordinate to `/AGENTS.md`, `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` and `LAYERSENTRY_EXECUTION_CONTRACT.md`

Current progress belongs in `LAYERSENTRY_CURRENT_STATUS.md`, `tools/layersentry/k8s/release-candidate-lane-b.json`, focused evidence and actual Git/workflow/live state. The historical expanded form of this specialist context remains available in Git history; do not restore it merely to regain narrative detail.

## 1. Authoritative scope

### In scope

1. the shared LayerSentry RKE2 lifecycle;
2. CAPI;
3. CAPC;
4. CAPRKE2;
5. RKE2;
6. primary CNI and optional qualified secondary networking;
7. CloudStack CCM/L4 integration;
8. CloudStack CSI and certified storage providers;
9. NodeDiskSet where required for node-owned scratch/cache disks;
10. central Flux package reconciliation;
11. Kubernetes-backed DBaaS;
12. Kubernetes-backed APaaS;
13. Streaming/Kafka when explicitly being qualified through this lifecycle;
14. LayerSentry UI/BFF/API contracts for those capabilities;
15. DB backup/restore/PITR only when advertised as DBaaS Day-2 capabilities;
16. security, RBAC, secrets, project/tenant isolation;
17. observability/status/reconciliation/failure recovery;
18. scale, replacement, upgrade, delete and air-gap behavior where claimed.

### Explicitly out of current scope

1. VM-native Single-OS DBaaS/APaaS;
2. cross-site RKE2 application DR;
3. Kubernetes-backed DBaaS DC->DR replication/promotion/failback;
4. APaaS cross-site DR;
5. RKE2 RPO/RTO, DR readiness, cross-site DNS/VIP switching or RKE2 DR UI;
6. general CloudStack IaaS/VM self-service;
7. object storage;
8. unrelated CloudStack UI;
9. hypervisor functionality unrelated to the Kubernetes lifecycle;
10. general rebranding;
11. ISO work except when an exact immutable/offline artifact blocks runtime qualification.

Dependencies may be inspected, but inspection must not expand the assigned source scope. The independent LayerSentry DC/DR workstream remains separate.

## 2. Two service models must not be merged

Kubernetes-backed services use:

```text
LayerSentry UI/BFF
 -> LayerSentry Kubernetes orchestration/reconciliation
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> Flux
 -> upstream DB/application packages/operators
```

VM-native Single-OS services use a different lifecycle:

```text
LayerSentry UI/API -> Go orchestration -> Ansible Runner -> Rocky Linux 9 VM
```

They may share CloudStack APIs, identity/RBAC, release trust and UI design language. They do not share lifecycle state machines, provider implementations or runtime certification evidence.

## 3. Ownership

- **CloudStack** owns KVM VM infrastructure, Sites/Zones, offerings, networks/VPCs, IPs, native LB/firewall/ACL, volumes, projects/accounts/domains and async resource state.
- **CAPI** owns Kubernetes cluster/Machine desired state.
- **CAPC** owns CloudStack resources created for CAPI Machines.
- **CAPRKE2** owns RKE2 bootstrap/control-plane lifecycle.
- **RKE2** is the Kubernetes distribution.
- **CCM** owns the selected Kubernetes `Service` type `LoadBalancer` integration.
- **CSI/storage provider** owns workload-volume lifecycle for its certified path.
- **Flux** owns LayerSentry package reconciliation.
- **upstream operators/controllers** own database/application-specific lifecycle.
- **LayerSentry** owns profiles, policy, compatibility, UI/BFF, composite operation status, audit and entitlement.

Never create two active controllers for the same lifecycle.

## 4. Release tuple and CAPC stop-loss

CAPI, CAPC, CAPRKE2, RKE2, OS/QCOW2, CNI, CCM, CSI and package/operator versions are a **single tested release tuple**. Exact current values and hard gates live in `tools/layersentry/k8s/release-candidate-lane-b.json`; do not copy volatile release state into this stable document.

Production requires actual reconciliation on CloudStack 4.22.1.1. Build compatibility or an upstream support matrix is not enough.

The preferred lifecycle remains CAPI/CAPC/CAPRKE2 because substantial source exists. If a bounded qualification campaign repeatedly cannot prove CloudStack resource creation, automatic RKE2 join, stable 6443/9345 and cluster `Ready`, and evidence shows CAPC maintenance is disproportionate, record a release decision and activate the approved fallback:

```text
native CloudStack APIs -> hardened QCOW2/cloud-init -> Ansible Runner -> RKE2 -> Flux
```

Never operate both owners for the same release.

## 5. Control-plane endpoint and networking

A LayerSentry RKE2 profile must provide stable reachability for the exact required control-plane ports, including Kubernetes API `6443` and RKE2 supervisor/registration `9345` for the current selected release.

Use one endpoint authority. Do not let separate controllers independently own different rules on the same VIP without an explicit lifecycle contract.

Primary CNI is selected from the release-qualified profile. CCM owns selected L4 LoadBalancer reconciliation. Gateway/API or other L7 controllers, when enabled, own L7 routing. Hardware ADC/WAF integration remains provider-specific and must not create competing VIP ownership.

Database wire protocols use appropriate L4/private exposure; do not place an HTTP WAF in front of PostgreSQL/MySQL/Redis/Kafka wire protocols merely because a WAF integration exists.

## 6. Storage and stateful-data safety

Durable DB/application data uses certified CSI/PVC storage. Node-attached disks are a different lifecycle and require explicit ownership.

### CSI/PVC requirements

Before stateful production promotion, prove the applicable path for:

- project-scoped provision/attach/mount/detach/delete;
- snapshot/restore if offered;
- repeated/idempotent resize if offered;
- restart/reconcile after timeout or ambiguous mutation;
- correct StorageClass/provider selection;
- tenant/project isolation;
- stateful Machine replacement with PVC/backend-volume survival and successful reattach.

### CAPC deletion safety

CAPC Machine deletion must distinguish CAPC-owned node resources from later-attached CSI workload volumes. Unowned/CSI volumes must never be destroyed merely because they are attached to the VM being replaced or deleted.

Automatic stateful remediation and unsafe scale-down remain blocked until destructive evidence proves the selected release behavior.

### NodeDiskSet

Node-owned extra CloudStack disks need explicit owner, volume ID, offering/tier, purpose, retain/delete policy, resize/replacement behavior and CAPI Machine relationship. Durable application/database data must not use arbitrary node disks. Scratch/cache is the first acceptable direct-node-disk class after qualification.

These are normal stateful-Kubernetes requirements. They do not imply cross-site DR.

## 7. Immutable node and offline release contract

Kubernetes nodes boot from versioned CloudStack QCOW2 templates. Do not hand-patch production nodes into divergent states; base OS/kernel/RKE2 changes produce a new image/template and controlled Machine rollout.

The logical LayerSentry platform carrier is:

`layersentry-platform-<release>.iso`

It may carry QCOW2, RKE2/CAPI/CAPC/CAPRKE2, CNI/CCM/CSI, Flux, OCI images/charts, DB/application packages, local RPM/DEB repositories, compatibility metadata, signatures, SBOM and provenance. Bundled means `AVAILABLE`, not installed.

No stable release may depend on moving tags/branches or uncontrolled Internet fetches. Air-gap claims require actual deny-all-egress proof for the exact selected artifacts.

## 8. Flux and upstream services

Central Flux is the LayerSentry package plane. It uses immutable/pinned sources and must reconcile remote workload clusters after restart without becoming a second cluster lifecycle owner.

Current upstream-first service choices:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- OpenBao from supported Helm/OCI content;
- Harbor from supported Helm/OCI content;
- Strimzi for Kafka.

LayerSentry integrates package source/HelmRelease, namespace/RBAC/project policy, certified storage/network exposure, local/offline artifacts, status/audit and E2E qualification.

Do not implement replacement DB operators, DB failover engines, backup/PITR engines, Kafka operators, Harbor/OpenBao controllers or replacement upstream UIs.

DB backup/restore/PITR may be exposed only after actual restore/data-integrity evidence for the selected operator/engine path. These capabilities are Day-2 data protection, not cross-site RKE2 DR.

## 9. UI/API production traceability

Do not score the whole UI as one optimistic percentage. Each advertised action must be traceable through the real vertical slice.

For each applicable action record:

`UI | API | AUTHORIZATION | BACKEND | RECONCILER/OPERATOR | K8S/STORAGE | PERSISTENCE | FAILURE PATH | TEST | LIVE EVIDENCE`

Minimum current audit surfaces:

### Kubernetes

- create/detail/health;
- nodes/node pools;
- scale;
- version/upgrade;
- delete.

### DBaaS

- catalog;
- create/detail;
- credentials/connectivity;
- health/monitoring;
- backup/restore/PITR where offered;
- resize/scale/topology where offered;
- upgrade;
- delete.

### APaaS

- catalog/deploy/detail;
- configuration/connectivity;
- scale where supported;
- logs/status/monitoring;
- upgrade/rollback where supported;
- delete.

No RKE2 application DR, failover/failback, RPO/RTO or DR UI is part of this current matrix.

A page, button or endpoint cannot promote a feature beyond the weakest evidenced layer in its vertical path.

## 10. Security and tenancy

Minimum production boundaries:

- server-side project/account authorization;
- no caller-written identity/role trust;
- scoped kubeconfig/provider credentials;
- no CloudStack admin secret in tenant workloads/browser/evidence;
- strict origin/CSRF/session handling for browser mutations;
- safe provider URLs/TLS/SSRF controls;
- namespace/project ownership and foreign-object adoption prevention;
- secret redaction;
- SELinux Enforcing and firewalld on certified Rocky profiles;
- signed/digested package and release trust where claimed.

## 11. Failure, reconciliation and evidence

Every mutating lifecycle must define:

- idempotency identity/fingerprint;
- durable intent before mutation where needed;
- authoritative observation after timeout/ambiguous result;
- bounded retry/backoff;
- no blind replay of destructive actions;
- restart/reconcile behavior;
- cleanup/retain semantics;
- exact failure reason and next safe action.

Valid statuses are the repository-wide statuses only. Source/CI cannot be promoted to live/production evidence.

For a production blocker record:

- blocker ID/subsystem;
- severity and current status;
- requirement and evidence;
- failure scenario/customer impact;
- owning layer;
- required fix;
- validation/live proof;
- engineering difficulty/dependency.

## 12. Production acceptance ceiling

A Kubernetes/Data Services release is not production-certified merely because the cluster is `Ready` or an operator is installed. The exact advertised scope must also prove required networking, storage/data safety, tenant isolation, package reconciliation, failure recovery, upgrades/deletes and live customer-facing vertical slices.

Current execution order and current gate are defined by Workstream E and `LAYERSENTRY_CURRENT_STATUS.md`; do not duplicate volatile sequencing here.

Use `LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md` only for the small set of exact integration constraints that are not already obvious from this contract.
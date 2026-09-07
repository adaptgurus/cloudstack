# LayerSentry V1 — Super Master Context

**Context schema:** 4.4  
**Role:** stable product/architecture contract only  
**Baseline:** Apache CloudStack 4.22.1.1 + LayerSentry KVM-first product layer  
**Execution policy:** `LAYERSENTRY_EXECUTION_CONTRACT.md`

This file contains only stable product architecture and non-negotiable production invariants. `AGENTS.md` defines hard AI/file/concurrency rules. `LAYERSENTRY_EXECUTION_CONTRACT.md` defines scheduling and current workstream activation. `LAYERSENTRY_CURRENT_STATUS.md`, module-specific status/release manifests and actual Git/workflow/live evidence define current progress. `LAYERSENTRY_PROGRESS_LEDGER.md` is historical evidence, not normal startup context.

## 1. Product objective

LayerSentry V1 is a commercial on-prem KVM private-cloud product built on Apache CloudStack, not a replacement scheduler.

Customer outcome:

```text
LayerSentry Portal
  -> VM / storage / network / image / bucket / backup
  -> LayerSentry-managed RKE2/Kubernetes
  -> Kubernetes-backed DBaaS/APaaS/Streaming
  -> VM-native Single-OS DBaaS/APaaS
  -> Backup/Recovery/DR
  -> support/operations/evidence
```

A focused audit or implementation assignment may narrow current work priority, but it does not silently redesign or merge unrelated product modules.

## 2. CloudStack is the IaaS authority

CloudStack remains authoritative for:

- KVM VM lifecycle;
- Sites/Zones, Pods, Clusters and Hosts;
- networks/VPCs, IPs, firewall/ACL and native LB;
- primary/secondary/object-storage integrations exposed by CloudStack;
- volumes, templates, ISOs, snapshots and native Backup & Recovery;
- account/domain/project/RBAC/quota;
- async jobs and native resource state.

LayerSentry must not create a second VM scheduler, tenancy/RBAC authority, quota authority, backup catalog or conflicting CloudStack resource inventory.

Implementation preference:

```text
native CloudStack 4.22.1.1 API
 -> supported provider/plugin/configuration
 -> mature ecosystem controller when it owns the lifecycle
 -> thin LayerSentry orchestration/policy/evidence
 -> narrow CloudStack core exception only when explicitly approved
```

## 3. Two DBaaS/APaaS architectures remain separate

### 3.1 Kubernetes-backed services

Use one LayerSentry-managed RKE2 lifecycle for user Kubernetes, Kubernetes DBaaS, APaaS and Streaming:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> central Flux
 -> selected upstream packages/operators
```

Ownership:

- CloudStack: IaaS;
- CAPI/CAPC: cluster/Machine desired state and CloudStack resources created for CAPI Machines;
- CAPRKE2: RKE2 bootstrap/control-plane lifecycle;
- CCM: qualified Kubernetes L4 LoadBalancer lifecycle;
- CSI: workload-volume lifecycle on the selected certified path;
- Flux: internal package reconciliation;
- upstream operators/controllers: database/application lifecycle;
- LayerSentry: UI/BFF, profiles, policy, compatibility, release channels, audit and composite operation status.

The approved release fallback, only after the formal CAPC stop-loss decision, is:

```text
native CloudStack APIs -> hardened QCOW2/cloud-init -> Ansible Runner -> RKE2 -> Flux
```

One release has one cluster lifecycle owner.

### 3.2 VM-native Single-OS services

This is a separate service model and does not depend on Kubernetes:

```text
LayerSentry UI/API
 -> Go orchestration/control
 -> Ansible Runner / ansible-core
 -> versioned roles/playbooks
 -> Rocky Linux 9 VM
```

Go owns authorization, schema/plan, confirmation, idempotency/locking, durable state/journal, secret references, execution/results, evidence and recovery state. Ansible owns guest repositories/packages, services, files/users, SELinux, firewalld, LVM/filesystems/mounts, VIP/networking and provider configuration.

The Kubernetes and Single-OS service models may share CloudStack APIs, identity/RBAC, release trust and UI design language, but they do not share lifecycle state machines or runtime certification evidence.

## 4. Kubernetes DBaaS/APaaS/Streaming

Current V1 upstream-first choices:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- OpenBao through supported Helm/OCI content;
- Harbor through supported Helm/OCI content;
- Strimzi for Kafka lifecycle.

LayerSentry supplies service catalog/access, project/namespace/RBAC policy, certified storage/network/VIP choices, compatibility/release selection, local/offline artifact references, health/status/audit integration and E2E qualification.

Do not replace mature upstream DB/Kafka/application lifecycle controllers, backup/PITR engines or upstream UIs merely to make the product look custom.

A catalog entry, UI screen, API endpoint, Helm chart, CRD or operator installation is not a completed managed service. Where applicable, production evidence must trace the complete vertical path:

```text
UI -> API -> authorization -> backend/orchestrator -> reconciler/operator
 -> Kubernetes/storage -> persistence/data safety -> failure/retry/UNKNOWN path
 -> tests -> live evidence
```

DB backup/restore/PITR remain in scope only when LayerSentry advertises those DBaaS Day-2 capabilities. They are not evidence of cross-site DR.

### Current V1 K8s DR boundary

Cross-site DR for RKE2 applications, Kubernetes-backed DBaaS and APaaS is **not part of the current K8s/Data Services implementation or audit scope**. Do not add RKE2 application DR, database DC->DR promotion, RKE2 failover/failback, RPO/RTO, cross-site DNS/VIP switching or RKE2 DR UI as Workstream-E completion gates unless the owner explicitly reopens that scope.

The independent LayerSentry DC/DR workstream remains valid for its own approved VM/CloudStack/provider-native scope.

## 5. Kubernetes storage and stateful-data safety

Excluding cross-site RKE2 DR does not remove normal stateful Kubernetes requirements.

Production qualification must still prove, where applicable:

- project/tenant isolation;
- PVC provision/attach/mount/detach/delete;
- snapshot/restore if offered;
- idempotent resize/expansion if offered;
- CAPC Machine deletion does not destroy unowned CSI workload volumes;
- stateful Machine replacement preserves and reattaches workload PVC/data;
- NodeDiskSet ownership for direct node-attached scratch/cache disks;
- durable database/application data uses certified CSI/PVC storage rather than arbitrary node disks;
- restart/reconciliation after ambiguous mutations.

CSI/PVC safety is a core Kubernetes production property, not a DR feature.

## 6. DC/DR/DRaaS

The independent V1 DC/DR path uses native CloudStack recovery first:

```text
healthy DC/DR infrastructure
 -> supported CloudStack B&R
 -> Recovery Point OLD
 -> mutate data
 -> Recovery Point NEW
 -> selected createVMFromBackup recovery
 -> isolated destination network
 -> exact root/data guest verification
 -> retry/RBAC/negative validation
 -> thin LayerSentry recovery orchestration
```

After native recovery passes, add only the provider-native low-RPO path required by the selected V1 storage profile, such as LINSTOR/DRBD, Ceph RBD mirroring or certified SAN-native replication. Planned failover/failback precedes witness/fencing/automatic failover.

This global DR workstream must not be interpreted as an implicit requirement to implement RKE2 application DR in Workstream E.

## 7. Bootstrap/control-plane HA

One temporary bootstrap server may seed initial deployment or catastrophic recovery. Production must operate after bootstrap is removed.

The target control-plane profile uses 3 Management VMs, 3 DB VMs and redundant LB/VIP nodes or a certified external ADC across real failure domains. Normal upgrades use the persistent management plane, not the temporary bootstrap server.

## 8. Release model

Use one logical signed platform carrier:

```text
layersentry-platform-<release>.iso
```

It may contain QCOW2, RKE2/CAPI/CAPC/CAPRKE2, CNI/CCM/CSI, Flux, OpenEverest/operators/images, OpenBao, Harbor, Strimzi/Kafka, approved security/observability/backup packages, RPM/DEB/local-registry content, compatibility metadata, checksums, signatures, SBOM and provenance.

Bundled means `AVAILABLE`, not installed. Flux installs selected Kubernetes packages.

## 9. Security invariants

Minimum:

- server-side authorization and tenant/project binding;
- strict input/schema validation;
- safe argv/typed API/module invocation;
- no untrusted shell interpolation/eval;
- parameterized SQL;
- path/archive/symlink safety;
- TLS verification and SSRF controls;
- finite timeouts/retries/concurrency;
- mutation idempotency/reconciliation;
- secrets never committed or emitted into browser/log/evidence;
- SELinux Enforcing and firewalld active on production Rocky profiles.

Do not disable security controls to make tests pass.

## 10. Evidence and production-readiness model

Valid statuses:

`DESIGN_DEFINED`, `SOURCE_COMPLETE`, `CI_VERIFIED`, `LIVE_VERIFIED`, `PRODUCTION_CERTIFIED`, `PARTIAL`, `PENDING`, `BLOCKED`, `UNKNOWN`, `NOT_TESTED`.

Source presence is not runtime proof. Unit tests are not E2E proof. A build artifact is not deployment proof. Documentation support is not exact-combination qualification.

A production blocker should identify, at minimum: subsystem, severity, current status, requirement, evidence, failure scenario/impact, owning layer, required fix, validation test/live proof and implementation difficulty/dependency.

Progress is measured by customer-operable vertical slices, not line/file/commit count or a single overall percentage.

## 11. Stable specialist authorities

Load only when the assigned module requires the detail:

- Kubernetes/RKE2: `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
- Kubernetes exact integration constraints: `LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md`;
- VM-native: `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
- DR: `LAYERSENTRY_DRAAS_ARCHITECTURE.md`;
- bootstrap/control-plane: `LAYERSENTRY_ANSIBLE_BOOTSTRAP_CONTROL_PLANE_CONTEXT.md`;
- security details: `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`.

Current source, module status/release manifests, workflow evidence and live state override stale specialist text.
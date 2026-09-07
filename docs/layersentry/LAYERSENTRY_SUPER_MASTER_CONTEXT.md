# LayerSentry V1 — Super Master Context

**Context schema:** 4.3  
**Role:** stable product/architecture contract only  
**Baseline:** Apache CloudStack 4.22.1.1 + LayerSentry KVM-first product layer  
**Execution policy:** `LAYERSENTRY_EXECUTION_CONTRACT.md`

This file intentionally avoids execution-routing, file-fence and current-status detail so every session does not pay to reread duplicated policy. `AGENTS.md` defines hard AI/file rules. `LAYERSENTRY_EXECUTION_CONTRACT.md` defines scheduling/ownership/lab shortcuts. `LAYERSENTRY_PROGRESS_LEDGER.md` + live evidence define current status.

## 1. Product objective

LayerSentry V1 is a commercial on-prem KVM private-cloud product built on Apache CloudStack, not a replacement scheduler.

Customer outcome:

```text
LayerSentry Portal
  -> VM / storage / network / image / bucket / backup
  -> LayerSentry-managed RKE2/Kubernetes
  -> Kubernetes DBaaS/APaaS/Streaming
  -> VM-native Single-OS DBaaS/APaaS
  -> Backup/Recovery/DR
  -> support/operations/evidence
```

Normal customers should not need raw CloudStack internals, YAML/kubectl, RKE2 join tokens, provider replication commands or guest installation scripts.

All product modules remain in canonical LayerSentry scope. A focused audit or execution assignment narrows only the **current work priority**; it must not delete, deprecate or silently redesign unrelated product modules.

## 2. CloudStack is the IaaS authority

CloudStack remains authoritative for:

- KVM VM lifecycle;
- Zones/Sites, Pods, Clusters and Hosts;
- networks/VPCs, IPs, firewall/ACL and native LB;
- primary/secondary/object-storage integrations exposed by CloudStack;
- volumes, templates, ISOs, snapshots and native Backup & Recovery;
- account/domain/project/RBAC/quota;
- async jobs and native resource state.

LayerSentry must not create a second VM scheduler, second tenancy/RBAC authority, second quota authority, second backup catalog or conflicting copy of CloudStack-owned state.

Implementation order:

```text
native CloudStack API
 -> supported provider/plugin/configuration
 -> ecosystem controller when it owns the lifecycle
 -> thin LayerSentry orchestration/policy/evidence
 -> narrow CloudStack core exception only when explicitly approved
```

## 3. LayerSentry-managed RKE2/Kubernetes

Use one cluster lifecycle for user Kubernetes, Data Services, APaaS and Streaming profiles:

```text
LayerSentry UI/BFF
      |
      v
     CAPI
   /      \
 CAPC    CAPRKE2
  |        |
CloudStack RKE2
      |
      v
 CNI / CCM / CSI
      |
      v
 central Flux
      |
      +-> selected upstream packages/operators
```

Ownership:

- CloudStack: IaaS;
- CAPI: cluster/machine desired state;
- CAPC: CloudStack resources created for CAPI Machines;
- CAPRKE2: RKE2 bootstrap/control-plane lifecycle;
- CCM: selected Kubernetes L4 LoadBalancer lifecycle;
- CSI: workload-volume lifecycle on the selected certified path;
- Flux: internal package reconciliation;
- upstream operators: application/database lifecycle;
- LayerSentry: UI/BFF, profiles, policy, compatibility, release channels, audit and composite operation state.

No separate cluster engines for DBaaS/APaaS/Streaming and no competing controllers for the same resource lifecycle.

The approved release fallback, if the CAPI/CAPC/CAPRKE2 path proves disproportionate to maintain, is:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

A release uses one cluster lifecycle owner.

### 3.1 Thin cross-module service-control contract

LayerSentry needs a consistent customer-facing lifecycle across IaaS, Kubernetes, DBaaS, APaaS, Streaming, Single-OS and DR, but this is a **contract over the existing owners**, not a new orchestration engine.

Reuse the existing LayerSentry durable operation/journal/reconciliation mechanisms. Do not introduce another generic workflow engine, desired-state database, resource inventory, scheduler or Kubernetes operator merely to wrap CAPI/CloudStack/Flux/upstream operators.

Customer-facing resources should normalize a small lifecycle vocabulary where applicable:

```text
CREATING / PROVISIONING
READY
DEGRADED
UPDATING
FAILED
DELETING
DELETED
UNKNOWN
```

A thin common operation envelope should expose, where applicable:

```text
resource identity + tenant/project
operation identity + action
lifecycle owner/provider
requested/desired intent reference
observed status
started/updated/completed timestamps
bounded retry/attempt information
failure reason / remediation pointer
evidence/audit correlation
```

The underlying authoritative state remains with its owner. For example, CAPI/CAPC remain authoritative for CAPI Machines, CloudStack for IaaS resources, Flux/operators for their managed objects, and provider-native DR for replication/promotion state. LayerSentry aggregates and reconciles customer-visible composite status; it does not duplicate those authorities.

A new shared abstraction is justified only when at least two active modules have proven duplicated behavior that cannot be cleanly supplied by an existing owner, and the abstraction demonstrably reduces source, testing and operational complexity.

## 4. Kubernetes DBaaS/APaaS/Streaming

These services run above the same RKE2/Flux substrate.

Current V1 upstream-first choices:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- OpenBao through supported Helm/OCI content;
- Harbor through supported Helm/OCI content;
- Strimzi for Kafka lifecycle.

LayerSentry supplies service catalog/access, project/namespace/RBAC policy, certified storage/network/VIP choices, compatibility/release selection, local/offline artifact references, health/status/audit integration and E2E qualification.

Do not replace mature upstream DB/Kafka/application lifecycle controllers merely to make the product look more custom. Upstream application UI rebranding is not a V1 requirement unless explicitly added later.

A catalog entry, Helm chart, operator installation or UI page is not itself a completed managed service. Promotion requires the applicable create/read/update/delete, authorization, storage/network, failure/reconciliation, backup/restore, upgrade/rollback, observability and DR acceptance evidence defined by the module contract.

## 5. VM-native Single-OS

This path is separate from Kubernetes services:

```text
LayerSentry UI/API
 -> Go orchestration/control
 -> Ansible Runner / ansible-core
 -> versioned roles/playbooks
 -> Rocky Linux 9 VM
```

Go owns authorization, schema/plan, confirmation, idempotency/locking, durable state/journal, secret references, execution/results, evidence and recovery state.

Ansible owns guest repositories/packages, services, files/users, SELinux, firewalld, LVM/filesystems/mounts, VIP/networking and DB/application configuration.

Bash/sh is not the product installation/configuration engine. Build/packaging wrappers may exist when they are not the runtime customer lifecycle.

## 6. DC/DR/DRaaS

V1 uses native CloudStack recovery first:

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

After native recovery passes, add only the provider-native low-RPO path required by the selected V1 storage profile, such as LINSTOR/DRBD, Ceph RBD mirroring or certified SAN-native replication.

Planned failover/failback is qualified before witness/fencing/automatic failover. Do not build a generic host block-copy engine when a storage provider already owns safe replication/promotion.

### 6.1 DR protection is composite, not VM-copy only

For Kubernetes DBaaS/APaaS and other stateful services, DR qualification must distinguish the independently authoritative state planes rather than treating VM recovery as application consistency:

```text
1. CloudStack infrastructure/recovery state
2. Kubernetes/CAPI/RKE2 control-plane state
3. database-native data/replication state where applicable
4. Kubernetes persistent-volume/storage-provider state
5. APaaS/application configuration and persistent state
6. service-access state: VIP/LB/Ingress/DNS/TLS
7. LayerSentry operation/audit/composite-status state
```

A LayerSentry protection/recovery object may aggregate these planes for UI, policy, RPO/RTO, audit and orchestration, but it must not become a competing replication engine. Promotion/failback must preserve provider ownership, fencing/split-brain safety, recovery-point correctness, health verification and explicit failure state.

## 7. Bootstrap/control-plane HA

One temporary bootstrap server may seed initial deployment or catastrophic recovery. Production must operate after bootstrap is removed.

The target control-plane profile uses 3 Management VMs, 3 DB VMs and redundant LB/VIP nodes or a certified external ADC across real failure domains. Normal upgrades use the persistent management plane, not the temporary bootstrap server.

## 8. V1 release model

Use one logical signed platform carrier:

```text
layersentry-platform-<release>.iso
```

It may contain QCOW2, RKE2/CAPI/CAPC/CAPRKE2, CNI/CCM/CSI, Flux, OpenEverest/operators/images, OpenBao, Harbor, Strimzi/Kafka, approved security/observability/backup packages, RPM/DEB/local registry content, compatibility metadata, checksums, signatures, SBOM and provenance.

Bundled means `AVAILABLE`, not installed. Flux installs selected packages. Adding an already-bundled package does not require reinstalling the ISO or cluster unless host/kernel capability changes.

## 9. Security invariants

Minimum:

- server-side authorization;
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

## 10. Evidence model

Valid statuses:

- `DESIGN_DEFINED`
- `SOURCE_COMPLETE`
- `CI_VERIFIED`
- `LIVE_VERIFIED`
- `PRODUCTION_CERTIFIED`
- `PARTIAL`
- `PENDING`
- `BLOCKED`
- `UNKNOWN`
- `NOT_TESTED`

Source presence is not runtime proof. Unit tests are not E2E proof. A build artifact is not deployed proof. Documentation support is not exact-combination qualification.

Progress is measured by complete customer-operable vertical slices, not line/file/commit count.

## 11. Stable specialist authorities

Use only when the assigned module requires them:

- Kubernetes/RKE2: `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
- VM-native: `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
- DR: `LAYERSENTRY_DRAAS_ARCHITECTURE.md`;
- bootstrap/control-plane: `LAYERSENTRY_ANSIBLE_BOOTSTRAP_CONTROL_PLANE_CONTEXT.md`;
- security details: `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`.

Current source/workflow/live evidence overrides stale specialist text.
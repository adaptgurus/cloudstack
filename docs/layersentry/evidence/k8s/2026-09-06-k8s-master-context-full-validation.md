# LayerSentry K8s / DBaaS / APaaS — Full Master-Context Validation

**Validation date:** 2026-09-06  
**Repository:** `adaptgurus/cloudstack`  
**Branch validated:** `layersentry/4.22.1.1-ui`  
**Baseline before this validation correction:** `75f2689a7d471d92758a7466eb2c2e4a94d06299`  
**Cloud target:** Apache CloudStack `4.22.1.1` + KVM  
**Result:** `CONDITIONAL_PASS / DESIGN_CORRECTED`  
**Runtime mutation:** none  
**Production certification:** **NOT established by this document**

## 1. Executive conclusion

The existing LayerSentry Kubernetes/DBaaS/APaaS Super Master Context is **architecturally sound but was not complete as-is**.

The high-level design remains the recommended direction:

```text
LayerSentry UI/API
  -> CAPI
      -> CAPC -> CloudStack 4.22.1.1 / KVM
      -> CAPRKE2 -> RKE2
  -> central Flux -> selected packages
  -> CloudStack native APIs for platform functions outside CAPC Machine ownership
  -> Gateway API / OEM controllers for L7/WAF
```

The source revalidation found four material gaps/nuances that must be carried as hard gates:

1. **Released CAPC/CAPRKE2 contract versions differ, but this is not automatic incompatibility.** There is an old fully released overlap at CAPI 1.9.x, and current CAPI provides a temporary v1beta1 infrastructure-provider compatibility bridge for testing CAPC 0.6.1 with modern CAPI/CAPRKE2.
2. **CAPC's CloudStack control-plane LB path exposes Kubernetes API 6443, while CAPRKE2 joins nodes on 9345.** LayerSentry must explicitly own/provide both ports.
3. **Current CAPC source still passes all attached DATADISK volume IDs into VM destruction.** This is a real data-safety blocker with CSI workload volumes and any additional node disks.
4. **Current CAPC models one deploy-time DiskOffering, not arbitrary multiple node disks.** Multiple Kubernetes StorageProfiles are fine, but multiple VM-attached node disks require an explicit LayerSentry/CAPC ownership model before production use.

The validation also found that CloudStack CSI `3.0.2` improves the project-scope situation compared with the earlier audit, but resize idempotency/CloudStack 4.22.1.1 behavior still requires qualification.

The specialist architecture therefore remains selected, with the mandatory companion:

`docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md`

---

## 2. Exact version/source findings

### 2.1 CAPC released line

Validated release:

```text
kubernetes-sigs/cluster-api-provider-cloudstack v0.6.1
```

Exact `go.mod`:

```text
sigs.k8s.io/cluster-api v1.9.6
k8s.io/api              v0.31.3
k8s.io/client-go        v0.31.3
```

CAPC `main` also still referenced CAPI `v1.9.6` during this validation.

CAPC CRD/config remains on the CAPI v1beta1 infrastructure contract label and has provider API versions through v1beta3.

### 2.2 CAPC modern-contract migration

Open upstream PR:

```text
kubernetes-sigs/cluster-api-provider-cloudstack #493
Upgrade to Cluster API v1.13 (v1beta2 contract) and promote API to v1beta4
```

Validated state during this audit:

```text
OPEN
UNMERGED
```

PR body states it bumps Cluster API to `1.13.2`, adopts the v1beta2 infrastructure contract and introduces a v1beta4 provider hub/storage version, with some unit/E2E evidence.

Decision:

- useful basis for a LayerSentry downstream test build if needed;
- **not** an upstream stable release;
- no production claim until a pinned commit is reviewed and passed through LayerSentry E2E/data-safety gates.

### 2.3 CAPRKE2 current line

Latest release validated during this audit:

```text
rancher/cluster-api-provider-rke2 v0.25.2
```

Exact `go.mod`:

```text
sigs.k8s.io/cluster-api v1.13.5
k8s.io/api              v0.35.4
k8s.io/client-go        v0.35.4
```

This is the clean current CAPI/CAPRKE2 control-plane pair for the LayerSentry modern lane.

### 2.4 CAPRKE2 released old-overlap line

Validated release:

```text
CAPRKE2 v0.15.0
```

Exact dependencies:

```text
sigs.k8s.io/cluster-api      v1.9.5
sigs.k8s.io/cluster-api/test v1.9.6
k8s.io/api                   v0.31.3
```

This creates an actual fully released overlap with CAPC `v0.6.1` around CAPI `1.9.x`.

### 2.5 Kubernetes version consequence

CAPI `1.9` supports workload Kubernetes only through `1.32` in the published version matrix.

Therefore this released overlap does **not** satisfy LayerSentry's intended current Kubernetes/RKE2 `1.36` direction.

CAPI `1.13.x` supports Kubernetes `1.36` workloads (from the applicable 1.13 patch line), making modern CAPI/CAPRKE2 the correct target family.

### 2.6 RKE2 candidate

Published RKE2 release validated:

```text
v1.36.4+rke2r1
```

This is a reasonable E0 candidate because:

- it is a real published RKE2 release;
- Kubernetes 1.36 fits the OpenEverest v1.16.2 support range;
- CAPI 1.13.x supports Kubernetes 1.36 workload clusters.

It is **not yet LayerSentry Certified**.

---

## 3. CAPI contract compatibility — corrected interpretation

Earlier wording risked implying:

> CAPC v0.6.1 uses an older CAPI contract and CAPRKE2 uses v1beta2, therefore they cannot run together.

That conclusion would be too strong.

Current CAPI v1beta2 contract documentation intentionally provides temporary backward compatibility for v1beta1 infrastructure providers. Therefore the modern released test lane can legitimately be:

```text
CAPI       1.13.5
CAPRKE2    0.25.2
CAPC       0.6.1
RKE2       1.36.4+rke2r1
CloudStack 4.22.1.1
```

This is a **qualification candidate**, not proof of compatibility.

Required E0 tests include:

- controller initialization;
- Cluster + CloudStackCluster reconciliation;
- CAPRKE2 control-plane references;
- Machine/MachineDeployment reconciliation;
- ClusterClass/topology behavior used by LayerSentry;
- create/delete/scale;
- upgrade;
- remediation;
- ExternalManaged/CloudStack synchronization if enabled;
- provider conditions/status conversion;
- repeated controller restarts.

Because the v1beta1 bridge is temporary/deprecated, the production roadmap must move to a CAPC v1beta2-contract release/downstream build before the bridge reaches its CAPI EOL.

---

## 4. RKE2 port 9345 — hard endpoint gap

### Source facts

CAPRKE2 source defines the RKE2 join/registration port:

```text
9345
```

and constructs worker/control-plane join URLs using:

```text
https://<registration-address>:9345
```

CAPC isolated-network source currently creates the CloudStack control-plane load-balancer rule for Kubernetes API traffic on:

```text
6443
```

and tracks one load-balancer rule ID.

### Consequence

A CAPC cluster that exposes only 6443 through its CloudStack control-plane VIP is insufficient proof for CAPRKE2 worker/control-plane automatic join.

### Required LayerSentry resolution

One endpoint authority must reconcile both:

```text
TCP 6443 -> all healthy RKE2 server nodes
TCP 9345 -> all healthy RKE2 server nodes
```

Preferred E0 implementation order:

1. evaluate a minimal CAPC endpoint enhancement/downstream patch that owns both rules on the CAPC-managed VIP;
2. if unsuitable, validate a dedicated LayerSentry endpoint provider/hardware/internal LB that owns both ports;
3. do not create a hidden second rule with ambiguous deletion/ownership semantics.

This must pass:

- first server bootstrap;
- second/third server join;
- worker join;
- server replacement;
- worker scale-up;
- VIP/LB failure;
- CAPC/controller restart;
- air-gap deployment.

---

## 5. CAPC Machine deletion and CSI data safety — current source confirms the risk

Upstream issue:

```text
kubernetes-sigs/cluster-api-provider-cloudstack #389
Potential data loss when used in combination with CloudStack CSI driver
```

The issue was closed stale/not-planned, not resolved by proof.

Current CAPC source still performs approximately:

```text
DestroyVMInstance
  -> ListVolumes(virtualmachineid, type=DATADISK)
  -> collect every returned volume ID
  -> DestroyVirtualMachine(..., volumeids=<all DATADISK IDs>)
```

This is direct source evidence that the LayerSentry production gate is necessary.

### Production rule

No stateful profile may be certified until deletion is ownership-safe.

CAPC/LayerSentry must distinguish:

```text
CAPC-owned node disk
CSI workload volume
LayerSentry NodeDiskSet disk
other externally attached disk
```

Only explicitly Machine-owned ephemeral/deploy-time volumes may be destroyed with the Machine.

### Required fix direction

Preferred model:

- explicit CloudStack resource tags/ownership metadata;
- CAPC tracks the IDs of volumes it created for the Machine;
- VM destroy includes only Machine-owned volumes;
- CSI/unowned volumes are detached/preserved according to their controller/policy;
- retention/deletion semantics are visible in audit/evidence.

### Required tests

- CSI PVC survives normal Machine delete;
- PVC survives MachineDeployment rollout;
- PVC survives scale-down candidate replacement;
- PVC survives MachineHealthCheck remediation;
- node scratch disk follows its intended delete policy;
- retain-policy node disk remains;
- repeated delete/reconcile is idempotent.

Until then:

```text
CAPC + stateful CSI automatic remediation = BLOCKED for production
DB worker automatic scale-down            = DISABLED
```

---

## 6. Multiple disks — exact supported interpretation

The user requirement to attach multiple disks/storage types to a cluster is retained.

### Supported architecture concept

A cluster can simultaneously expose many storage profiles:

```text
CloudStack CSI block
NFS CSI / SharedFS RWX
NetApp CSI
Dell CSI
HPE CSI
Pure CSI
other certified OEM CSI
node-local/scratch storage
```

Each workload can have multiple PVCs and StorageClasses.

### Current CAPC limitation

Current `CloudStackMachineSpec` has one deploy-time `DiskOffering` field, not an arbitrary array of independently managed node disks.

### Required LayerSentry abstraction

For direct worker disks, implement an explicit node-disk lifecycle object such as:

```text
NodeDiskSet
```

with:

- owner node pool;
- volume IDs;
- offering/tier/size/IOPS;
- purpose;
- attach state/device identity;
- retain/delete policy;
- resize policy;
- encryption;
- tags;
- replacement/reconcile semantics.

### Initial certification rule

- persistent DB/application storage: CSI/PVC;
- additional VM-attached disks: advanced/PENDING until ownership fix;
- scratch/cache is the first appropriate direct-node-disk use case;
- never represent one ordinary CloudStack block volume as a safe multi-writer disk for all nodes.

---

## 7. CloudStack CSI v3.0.2 — updated assessment

Latest validated release:

```text
cloudstack-csi-3.0.2
published 2026-09-01
```

Merged change in PR #7:

```text
csClient.DefaultOptions(cloudstack.WithProject(projectID))
```

This means the exact old `Count:0` project lookup failure cannot simply be assumed to remain unchanged in v3.0.2.

However, exact `ExpandVolume` source in v3.0.2 still:

- looks up the current size;
- always calls `ResizeVolume` for the requested size;
- does not visibly return early when current size is already greater/equal to requested size.

Therefore:

```text
project-aware lookup: improved by v3.0.2, must test
resize idempotency:    still a qualification concern
```

LayerSentry does not enable project PVC auto-grow until it proves:

- create PVC inside CloudStack project;
- attach/detach;
- expand online;
- repeated ControllerExpandVolume/reconcile;
- controller restart during expansion;
- already-expanded backend convergence;
- filesystem resize;
- no cross-project visibility/leak.

---

## 8. CloudStack storage model validation

The master-context storage separation remains correct.

### CloudStack Disk Offering `shared`

Means shared primary-storage type, **not** one guest block volume safely attached read/write to all Kubernetes nodes.

### CloudStack normal block data volume

Treat as a block volume with single-owner attachment semantics unless an exact feature/provider explicitly proves otherwise.

### CloudStack Shared FileSystem

CloudStack 4.22 includes a distinct Shared FileSystem API/service family. It is the native CloudStack path for managed network-attached shared filesystem/NFS behavior.

LayerSentry may consume it as:

- static NFS PV; or
- NFS CSI-backed dynamic subdirectories after exact qualification.

### RWX policy

General shared RWX storage:

```text
CloudStack SharedFS/NFS
or
certified OEM file/CSI
```

Advanced raw shared block requires an explicit certified clustered/multi-writer filesystem/storage design. Ordinary XFS/ext4 on a raw multi-attached LUN is prohibited.

---

## 9. QCOW2 / ISO / late-package model validation

Retained without architectural correction.

### QCOW2

Actual immutable-infrastructure node runtime for CloudStack/KVM.

Contains generic host capabilities such as:

- `lsscsi`;
- iSCSI tools;
- multipath tools;
- NVMe tools;
- NFS client;
- diagnostics;
- RKE2-version-specific artifacts according to the selected offline strategy.

Unneeded services remain inactive.

### Offline ISO/bundle

Signed artifact carrier/catalog, not the normal node boot/install medium.

Contains:

- QCOW2 images;
- OCI images;
- Helm/OCI artifacts;
- RPM/DEB repositories;
- CAPI/CAPC/CAPRKE2/Flux;
- CNI/CSI/add-ons;
- Data Services artifacts;
- signatures/SBOM/provenance/compatibility metadata.

### Late package installation

Retained.

A package present in the local release catalog is not installed until selected. Later GUI installation does not require reinstalling RKE2 or reattaching/reinstalling the original ISO.

Host/kernel dependencies are the exception: if a new package needs a new kernel module/driver, LayerSentry performs a node-image/MachineTemplate rollout first.

---

## 10. RKE2 networking validation

RKE2 current documentation continues to support the selected CNI model:

- Canal;
- Cilium;
- Calico;
- Flannel;
- Multus as secondary CNI.

The master-context policy remains correct:

- select one primary CNI at creation;
- Cilium may be the LayerSentry advanced/security default after exact certification;
- do not install multiple primary CNIs concurrently;
- do not treat primary-CNI migration as an ordinary one-click package update;
- include required air-gap image artifacts for the selected CNI.

Flannel should not become the hardened/security default if the required NetworkPolicy behavior is absent for the selected RKE2 profile.

---

## 11. Central Flux validation

The internal package-management decision remains valid.

Flux Helm Controller supports remote cluster reconciliation through `spec.kubeConfig`, and its documentation explicitly describes using CAPI's generated `<cluster-name>-kubeconfig` Secret.

The following design is retained:

```text
LayerSentry management cluster
  -> Flux source/helm controller
      -> remote CAPI workload cluster
```

Benefits retained:

- OCI source support;
- Helm release lifecycle;
- dependencies;
- drift correction;
- remediation;
- no mandatory tenant-facing GitOps UI.

Tenant Argo CD/Flux remains independent optional functionality and cannot own LayerSentry internal package state.

No Rancher/Fleet/GitLab/Gitea/AWX/CAAPH dependency is added merely to perform the same package reconciliation.

---

## 12. DBaaS / OpenEverest validation

Exact OpenEverest `v1.16.2` versioned support documentation was checked.

It states:

```text
Kubernetes supported: 1.33 - 1.36
Air-gapped: not currently supported upstream
```

It lists current Percona operator lines for PXC, PSMDB and PostgreSQL.

Therefore the LayerSentry design remains correct:

- OpenEverest does not provision the underlying RKE2 cluster;
- LayerSentry provisions/owns Data Services Kubernetes;
- OpenEverest is a DB control component after qualification;
- LayerSentry branding is customer-facing;
- upstream air-gap support is not claimed;
- a LayerSentry offline OpenEverest profile requires complete mirrored dependency inventory and deny-all-egress tests;
- Redis/Valkey remains a separate provider/operator until a stable supported OpenEverest provider model justifies consolidation.

The target `RKE2/Kubernetes 1.36.x` is compatible with the OpenEverest v1.16.2 documented Kubernetes range, but the complete LayerSentry combination still needs E2E tests.

---

## 13. APaaS validation status

### OpenBao

Architecture retained:

- HA profile;
- multiple replicas;
- integrated Raft where selected;
- TLS;
- anti-affinity;
- persistent storage;
- snapshot/restore;
- explicit seal/unseal/key-management workflow.

No exact OpenBao version is frozen by the stable master context. The release manifest must pin the version and test its exact Helm/HA behavior.

### Harbor

Architecture retained:

- Harbor is tenant/APaaS registry, not bootstrap registry;
- platform bootstrap registry remains independent;
- production HA dependencies/persistence must be exact-release qualified;
- external DB/Redis integration may consume LayerSentry Data Services only when dependency ordering and recovery are proven.

No production version is implied by this document.

---

## 14. Kafka / Strimzi validation status

Architecture retained:

- Strimzi owns Kafka lifecycle;
- LayerSentry does not write its own Kafka operator;
- production may use dedicated Kafka workers;
- external listener mode may require bootstrap + per-broker endpoints/VIPs;
- LayerSentry calculates endpoint requirement from the exact Strimzi listener configuration;
- upgrades use explicit operator/broker compatibility paths.

Exact Strimzi/Kafka versions remain release-manifest inputs and must be revalidated before implementation.

---

## 15. GPU / NVIDIA validation status

Architecture retained with qualification gates:

- CPU workers do not load an active NVIDIA kernel driver by default;
- GPU worker pool uses a GPU-specific QCOW2 or another specifically certified driver lifecycle;
- GPU Operator/device plugin/toolkit/DCGM artifacts may be mirrored offline subject to licensing;
- preinstalled driver and GPU Operator driver-management responsibilities must not conflict;
- NVMe/RDMA storage and NVIDIA GPUDirect RDMA are separate capabilities;
- GPUDirect is not claimed on generic CloudStack/KVM until exact GPU/NIC/driver/virtualization/storage certification passes.

No GPU/vGPU/GPUDirect production claim is made by the master context.

---

## 16. L4 / L7 / VIP / WAF validation

Architecture retained.

### CloudStack

Owns infrastructure IP/VIP inventory, native L4 LB/firewall/ACL/NAT/VPC primitives and InternalLB where the selected offering/topology supports it.

Native CloudStack LB is not represented as an AWS-style L7 ALB.

### CloudStack Kubernetes Provider/CCM

Latest release identified during the broader research is `v1.2.0`; it provides Kubernetes `LoadBalancer` to CloudStack L4 reconciliation improvements including selected `loadBalancerIP` behavior and VPC/source-CIDR enhancements.

LayerSentry tracks the deprecated Kubernetes `spec.loadBalancerIP` semantics and must migrate to a provider-specific supported mechanism when upstream implements one.

### Gateway API

Remains LayerSentry L7 abstraction.

### Multi-VIP

Retained:

- one application/backend may have multiple Frontends;
- one externally managed VIP = one LayerSentry Frontend lifecycle object;
- several Frontends may target one backend;
- a shared L7 Gateway VIP may host several hostnames where policy permits.

### Hardware WAF/ADC

Retained as provider adapters using vendor-native Kubernetes/API integrations. F5/Radware/Imperva/etc. are not declared certified until exact product/version/API/air-gap tests pass.

If hardware ADC is VIP authority, avoid an unnecessary second CloudStack load-balancer hop unless required by network design.

---

## 17. Alternatives audit — completion of the original research requirement

### Cozystack

Current architecture validates the useful pattern rather than embedding Cozystack wholesale:

```text
OCI package artifacts + declarative package lifecycle + Flux
```

LayerSentry keeps CloudStack as IaaS and CAPI/RKE2 as cluster lifecycle authority.

### Otomi / Akamai App Platform

Retained as a platform-UX reference for curated apps, policy, observability/security and Gateway API patterns. It is not required in the LayerSentry critical path.

### KubeBlocks

Current repository license is AGPL-3.0.

Do not embed/copy its code into a closed LayerSentry product without explicit legal/licensing approval. Use architectural ideas only unless the licensing decision changes.

### KubeDB Platform

Remains a credible commercial white-label/offline DBaaS alternative.

OpenEverest remains the open-source-control direction, but a future commercial/OEM decision may select KubeDB if it materially reduces product risk/time-to-market and economics are acceptable.

### Rancher/Turtles

Not mandatory for V1. CAPRKE2 can be used directly. Adding Rancher would create another platform/control-plane dependency and does not remove CAPC qualification work.

---

## 18. Upgrade-after-three-months audit

The original separation is retained and is a strong production property.

### Package/chart/operator-only change

```text
new signed OCI/Helm artifact
 -> compatibility gate
 -> Flux rollout/remediation
```

No node rebuild unless host dependency changed.

### RKE2/kernel/base-OS/host-driver change

```text
new QCOW2
 -> CloudStack template
 -> new CAPI MachineTemplate/topology
 -> staged node replacement
```

### CNI major migration

Certified migration or blue/green cluster; not normal Helm upgrade.

### CSI migration/major

Storage data-safety migration with rollback/recovery proof.

### Database engine/operator

Separate maintenance path from Kubernetes/CSI.

### CAPC contract migration

Treat as a management/provider migration requiring:

- CRD/webhook conversion validation;
- backup of management-cluster objects;
- provider rollout;
- existing cluster reconciliation proof;
- create/scale/delete/upgrade regression;
- no orphaned CloudStack resources.

The temporary v1beta1 bridge must not become an unmanaged long-term dependency.

---

## 19. Final validation status matrix

| Area | Result | Meaning |
| --- | --- | --- |
| CloudStack 4.22.1.1 + KVM authority | PASS / architecture | retained |
| CAPI-first lifecycle | PASS / architecture | retained |
| CAPC exact production tuple | PENDING | E0 required |
| CAPRKE2 automatic join | PASS / source concept | exact integration pending |
| CAPC + CAPRKE2 9345 endpoint | **BLOCKER** | explicit fix/endpoint provider required |
| CAPC + CSI Machine delete safety | **BLOCKER** | current source still unsafe pattern |
| Multiple StorageProfiles/PVCs | PASS / architecture | provider certification per profile |
| Multiple direct node disks | PENDING/BLOCKED | NodeDiskSet/ownership model required |
| CloudStack SharedFS/NFS RWX model | PASS / architecture | exact E2E/failure tests required |
| CloudStack CSI 3.0.2 | PENDING | project/resize/idempotency E2E required |
| QCOW2 + offline ISO split | PASS / architecture | release builder still implementation work |
| Late package install | PASS / architecture | Flux/package implementation pending |
| Central Flux | PASS / source capability | security/E2E pending |
| OpenEverest v1.16.2 K8s 1.33-1.36 | PASS / documented | exact integration pending |
| OpenEverest air-gap | NOT upstream-supported | LayerSentry engineering/E2E required |
| Redis/Valkey provider | DESIGN_DEFINED | operator/version to select |
| OpenBao | DESIGN_DEFINED | exact version certification required |
| Harbor | DESIGN_DEFINED | exact version/HA certification required |
| Strimzi/Kafka | DESIGN_DEFINED | exact version certification required |
| GPU/NVIDIA | DESIGN_DEFINED | hardware/license/E2E required |
| NVMe/RDMA | ADVANCED/PENDING | exact hardware/OEM path required |
| GPUDirect RDMA | NOT CERTIFIED | explicit qualification required |
| CloudStack L4 / Gateway L7 split | PASS / architecture | provider E2E required |
| Hardware WAF/ADC | DESIGN_DEFINED | vendor-by-vendor certification |
| DBaaS production | NOT CERTIFIED | storage/failover/backup/PITR required |
| Full air-gap product | NOT CERTIFIED | deny-all-egress lifecycle proof required |

---

## 20. Required E0 execution order

Do not start DBaaS implementation before this vertical slice is safe.

### Step 1 — build candidate management/provider tuple

Test first:

```text
CloudStack 4.22.1.1
CAPI 1.13.5
CAPRKE2 0.25.2
CAPC 0.6.1
RKE2 1.36.4+rke2r1
```

using the CAPI temporary v1beta1-infrastructure compatibility bridge.

### Step 2 — solve RKE2 endpoint

Prove stable 6443 + 9345 endpoint and automatic 3-server + worker joins.

### Step 3 — test CAPC lifecycle without workload CSI

- create;
- scale;
- replace;
- delete;
- controller restart;
- CloudStack management interruption.

### Step 4 — fix/test CAPC volume ownership

Do not proceed to stateful DBaaS until workload PVC survives Machine deletion/replacement.

### Step 5 — qualify one storage path

Prefer one safest production path first. Add CloudStack CSI only after its exact safety matrix passes, or use an OEM CSI whose exact combination can be validated.

### Step 6 — fully offline test

Deny all Internet egress and repeat create/scale/repair/replace/upgrade/package operations.

### Step 7 — compare modern CAPC contract lane

Build/test upstream PR #493 or its then-current/released successor. If materially safer/better and compatible, select the modern contract lane and record the exact commit/release.

### Step 8 — only then enable DBaaS vertical slice

PostgreSQL first, with backup/restore/PITR/failure/worker replacement/data-integrity tests.

---

## 21. Final decision

The LayerSentry K8s/DBaaS/APaaS master architecture is **retained**, but the statement “validated as-is with no changes” would be inaccurate.

The correct status is:

> **Architecture retained and completed with explicit compatibility, endpoint and data-ownership gates.**

No redesign to Rancher, native CKS, AWX, XaaS or a custom full Kubernetes lifecycle engine is justified at this point.

The next objective evidence must come from E0 implementation on CloudStack `4.22.1.1`, not another architecture rewrite.

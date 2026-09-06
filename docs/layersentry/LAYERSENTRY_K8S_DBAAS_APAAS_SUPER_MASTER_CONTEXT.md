# LayerSentry Kubernetes, DBaaS, APaaS and Streaming — Super Master Context

**Status:** `DESIGN_DEFINED` until implementation/CI/live evidence promotes an exact release/profile  
**Scope:** LayerSentry-managed Kubernetes, DBaaS, APaaS, Streaming, package catalog, cluster storage/networking and related self-service UX  
**Cloud baseline:** Apache CloudStack `4.22.1.1` + native KVM  
**Authority:** specialist stable architecture/engineering contract subordinate to repository `AGENTS.md` and `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`

This document is deliberately scoped. It does **not** replace or weaken the existing VM, Backup/DR, appliance, security, release, control-plane, RBAC, KVM, or CloudStack-core-preservation contracts. If a rule in this document does not apply to Kubernetes/Data Services/APaaS/Streaming, the existing canonical/specialist rule remains unchanged.

Current branch HEADs, workflow IDs, live IPs, credentials, runtime health, current artifacts and test outcomes do not belong here. They belong in `LAYERSENTRY_PROGRESS_LEDGER.md` and immutable evidence.

---

## 0. Authority, non-interference and anti-hallucination rules

1. Read repository `/AGENTS.md`, `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`, the current Progress Ledger and the assigned workstream before changing source/runtime.
2. This file is authoritative only for the Kubernetes/DBaaS/APaaS/Streaming module.
3. Do not rewrite unrelated existing master contexts merely to make this module fit.
4. Do not change CloudStack Java APIs/contracts, database schema, KVM agent, scheduler, RBAC, async-job semantics, network/storage orchestration or upstream hypervisor implementations for convenience.
5. Use exact CloudStack `4.22.1.1` source/API/docs for CloudStack capability claims. Do not infer `4.22.1.1` behavior from `/latest/` or a later release.
6. For CAPI/CAPC/CAPRKE2/RKE2/Flux/OpenEverest/CSI/CNI/OEM integrations, verify exact versions, source, release notes, issues and compatibility before implementation or upgrade.
7. A documented capability is not runtime proof. An upstream matrix is not proof of the exact LayerSentry combination. A successful build is not deployment proof.
8. Use governed status labels from the canonical context. In particular, this document itself does not make any capability `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`.
9. If sources conflict, do not average or guess. Record the conflict, identify the authoritative layer, test the exact combination and keep status `UNKNOWN`, `PENDING`, `NOT_TESTED` or `BLOCKED` until resolved.
10. Every claim involving shared block access, storage resize, CSI behavior, VIP ownership, WAF/ADC integration, air-gap operation, upgrade/rollback or data safety requires exact-source and destructive E2E validation before production certification.

### Current research-risk notes that must remain qualification gates

These are reasons for caution, not permanent version locks:

- core Cluster API has current workload support for recent Kubernetes releases, but provider compatibility still governs the usable fleet version;
- CAPRKE2 is actively maintained and has current CAPI integration, but must be paired with a compatible CAPI/CAPC release tuple;
- upstream CAPC's published tested matrix has historically lagged the target CloudStack `4.22.1.1`/latest Kubernetes combination; LayerSentry must qualify the exact tuple instead of assuming compatibility;
- the community CloudStack CSI driver is KVM-oriented but has known/open project-scoped expansion concerns in current upstream issue history; LayerSentry must not advertise project PVC auto-expansion until the exact selected build passes the project test matrix;
- OpenEverest stable releases are suitable for investigation as a DBaaS control component, but current upstream support documentation has explicitly stated that air-gapped environments are not supported; any LayerSentry offline OpenEverest capability is therefore a LayerSentry-engineered and LayerSentry-certified distribution, not an inherited upstream support claim.

Revalidate these findings whenever target versions change.

---

## 1. Product scope and names

The customer-facing services governed by this module are:

- **LayerSentry K8s** — user/self-service RKE2 clusters on CloudStack/KVM;
- **LayerSentry DBaaS** — managed databases on a LayerSentry-managed RKE2 Data Services cluster;
- **LayerSentry APaaS** — application platform services such as OpenBao and Harbor;
- **LayerSentry Streaming** — Kafka through Strimzi and future certified streaming services.

These are now valid LayerSentry product modules. They are not implemented as CloudStack-native DBaaS/APaaS backend features and must not be forced into CloudStack core.

LayerSentry customer branding remains LayerSentry. Upstream product names may remain in legal attribution, diagnostics, source/package metadata and support views where required, but the normal customer workflow should present LayerSentry product terminology.

---

## 2. Frozen high-level architecture

The selected architecture is:

```text
                         LayerSentry Self-Service UI
                                   |
                                   v
                         LayerSentry API / BFF
                  policy / profiles / compatibility / audit
                                   |
                 +-----------------+------------------+
                 |                 |                  |
                 v                 v                  v
       CloudStack native API   Kubernetes API     Package API
           4.22.1.1                |                  |
                 |                 |                  v
                 |      LayerSentry Management RKE2  Central Flux
                 |                 |                  |
                 |                 v                  |
                 |                CAPI                |
                 |          +------+-------+          |
                 |          |              |          |
                 |         CAPC         CAPRKE2       |
                 |          |              |          |
                 +----------+--------------+----------+
                            |
                     Apache CloudStack
                            |
                           KVM
                            |
                  RKE2 workload clusters
                            |
             +--------------+----------------+
             |              |                |
          K8s users       DBaaS          APaaS/Streaming
```

### Ownership rules

- **CloudStack** remains authoritative for KVM VM infrastructure, service/disk offerings, volumes, networks/VPCs, IPs, native LB/firewall/ACL resources, projects/accounts/domains, host/storage placement and async jobs.
- **CAPI** is the Kubernetes Machine/cluster desired-state lifecycle layer.
- **CAPC** owns CloudStack VMs/resources created as CAPI Machines. LayerSentry must not independently mutate/delete those Machines behind CAPC.
- **CAPRKE2** owns RKE2 control-plane/bootstrap lifecycle for CAPI-managed clusters.
- **RKE2** remains the Kubernetes distribution for LayerSentry-managed clusters.
- **CloudStack Kubernetes Provider/CCM** owns supported Kubernetes `Service` type `LoadBalancer` reconciliation to CloudStack L4 resources where that provider path is selected.
- **Gateway API controller** owns L7 application routing.
- **Flux** is the internal LayerSentry package reconciler.
- **Database/application operators** own application-specific Day-2 lifecycle.
- **LayerSentry** owns the GUI, profiles, policy, compatibility matrix, release channels, workflow state, entitlement, audit, provider abstraction and customer experience.
- **Ansible Runner/AWX** are imperative operational tools only where declarative controllers are not the right boundary.
- **XaaS** is optional/thin integration or custom-action bridging; it is not the RKE2/KVM lifecycle foundation.

Never create two active controllers for the same resource lifecycle.

---

## 3. Why CAPI is selected and fallback rule

Preferred production direction:

```text
LayerSentry -> CAPI -> CAPC + CAPRKE2 -> CloudStack/KVM + RKE2
```

Benefits:

- declarative cluster/machine desired state;
- MachineDeployment/node-pool lifecycle;
- rolling replacement semantics;
- health/remediation primitives;
- cluster autoscaler integration;
- reduced LayerSentry custom lifecycle code;
- cleaner recovery after interrupted operations;
- upgrade policy expressed through versioned templates/topology rather than imperative SSH pipelines.

### CAPC production gate

CAPI is the selected architecture, but CAPC is **not assumed production-certified** for CloudStack `4.22.1.1` merely because it can build/run.

Before GA, LayerSentry must certify the exact tuple:

```text
CloudStack 4.22.1.1
CAPI <pinned certified version>
CAPC <pinned LayerSentry-qualified version/commit>
CAPRKE2 <pinned compatible version>
RKE2 <pinned certified version>
OS image <pinned digest>
CNI/CCM/CSI <pinned versions>
```

If upstream CAPC lacks a required fix, maintain the smallest possible LayerSentry downstream patch, document the delta, test it, and upstream the change when practical. Do not recreate Cluster API from scratch.

### Fallback

If CAPC cannot pass the production data-safety/lifecycle gates for an exact release, the approved fallback is:

```text
LayerSentry durable workflow engine
 -> CloudStack native APIs
 -> hardened QCOW2
 -> Ansible Runner/cloud-init
 -> RKE2
```

The fallback must remain bounded and must not be implemented in parallel as a second active owner unless a release explicitly selects it.

---

## 4. Management cluster and bootstrap

Production LayerSentry requires a dedicated management RKE2 environment for CAPI and central Flux. It must not depend on a customer workload cluster.

Recommended conceptual profile:

- 3 RKE2 server/control-plane nodes;
- optional small dedicated management workers according to capacity/isolation policy;
- CAPI core;
- CAPC;
- CAPRKE2;
- Flux source-controller/helm-controller and other approved internal controllers;
- LayerSentry Kubernetes orchestration services;
- module observability/audit components.

The **first management cluster** is bootstrapped through a bounded, deterministic native CloudStack/API + image/cloud-init/Runner path. After CAPI is healthy, tenant/Data Services clusters use CAPI.

The management cluster itself requires backup, restore and rescue procedures. If it runs on the CloudStack estate it manages, it must have an out-of-band recovery path consistent with the global control-plane recovery policy.

---

## 5. Kubernetes version and release-channel policy

Do not expose arbitrary upstream Kubernetes versions directly to production customers.

LayerSentry publishes curated release channels:

- **Certified / Stable** — exact LayerSentry-qualified RKE2/Kubernetes tuple, normally not the upstream minor on day one;
- **Preview** — newer upstream/RKE2 minor for lab/POC/qualification;
- **Extended** — older supported LayerSentry-certified minor for controlled migration windows.

Production policy should generally track a provider-certified N/N-1 window rather than immediately exposing upstream `latest`.

Rules:

1. no `latest` container tags or moving Git branches in stable releases;
2. every version appears in the immutable release manifest;
3. Kubernetes minor upgrades follow supported skew/path rules and do not skip required intermediate minors;
4. management-cluster compatibility and workload-cluster compatibility are checked separately;
5. CNI, CSI, CCM, Gateway, security, DB operators, Strimzi and storage-provider compatibility must pass before a Kubernetes minor becomes LayerSentry Certified.

---

## 6. ClusterClass and node-pool model

Use a small set of LayerSentry ClusterClass/topology profiles rather than generating ungoverned per-cluster manifests.

Candidate profiles:

- `layersentry-standard-rke2`;
- `layersentry-secure-rke2`;
- `layersentry-dbaas-rke2`;
- `layersentry-kafka-rke2`;
- `layersentry-gpu-rke2`;
- `layersentry-custom-rke2` for advanced/admin scope.

Node pools are modeled as CAPI MachineDeployments/appropriate provider objects and may include:

- general workers;
- DB workers;
- Kafka workers;
- APaaS/platform workers;
- GPU workers;
- specialized storage/network worker pools.

Each pool can carry labels, taints, placement rules, CloudStack service offering, image/template, additional disks and network/storage policy.

Managed clusters use **automatic join only**. CAPRKE2 generates/uses the server URL/token/bootstrap data. Users do not manually SSH nodes or paste RKE2 join tokens for a normal LayerSentry-managed cluster. Manual/imported nodes, if supported later, are a separate explicit mode without normal CAPI lifecycle guarantees.

RKE2 control-plane endpoint design must account for both Kubernetes API traffic and RKE2 supervisor/join traffic, including the relevant ports required by the exact RKE2/CAPRKE2 release.

---

## 7. QCOW2 versus ISO — immutable infrastructure contract

LayerSentry uses **both**, for different purposes.

### QCOW2

Actual CloudStack/KVM Kubernetes nodes boot from versioned QCOW2 templates.

```text
LS-RKE2-<OS>-<RKE2>-<image-rev>.qcow2
```

Treat node infrastructure as immutable:

- do not hand-patch production nodes into divergent states;
- rebuild a new QCOW2 when kernel/RKE2/host-driver/base-OS behavior changes materially;
- register a new CloudStack template;
- create a new CAPI MachineTemplate/topology version;
- roll nodes through CAPI.

### Offline ISO

The ISO is a signed LayerSentry **release repository/carrier**, not the normal per-node OS installer.

It transports:

- QCOW2 templates;
- RKE2 binaries/images;
- CAPI/CAPC/CAPRKE2 artifacts;
- OCI images;
- Helm/OCI charts;
- RPM/DEB repositories;
- Flux components;
- CSI/CNI/operator/application packages;
- NVIDIA artifacts where licensed/approved;
- SBOM/provenance/checksums/signatures;
- compatibility and upgrade metadata.

Import the ISO into LayerSentry, verify it, populate local artifact services, then the ISO can be detached/removed. Users do not reinstall the ISO to add a package later.

### Incremental updates

Support signed incremental update bundles for package/security/chart/operator updates that do not require a whole platform ISO refresh. The exact format must be versioned and protected by the global release/signature contract.

---

## 8. Universal CPU node image

The standard RKE2 QCOW2 contains generic host capabilities and troubleshooting tooling, not every Kubernetes CSI/controller running by default.

Baseline host packages/tools should include the exact OS equivalents of:

- cloud-init;
- qemu-guest-agent;
- iSCSI initiator tooling;
- `lsscsi`;
- `sg3-utils`;
- device-mapper/multipath tooling;
- `nvme-cli`;
- NFS client tooling;
- `lvm2`;
- `mdadm`;
- XFS/ext filesystem utilities;
- cryptsetup where part of the certified profile;
- `fio`, `ioping`, `smartmontools`, `sysstat`, `iotop` or approved equivalents;
- `iproute2`, `ethtool`, `conntrack`, `socat`, `tcpdump`, `mtr`, DNS/network diagnostics;
- `curl`, `jq`, `yq`, `openssl`, `rsync` where approved;
- RDMA userspace tools only when they do not create unsafe defaults and the kernel/profile supports them.

Relevant kernel modules must be present for supported profiles. Services such as multipath/iSCSI sessions/RDMA-specific configuration are enabled only by a selected validated StorageHostProfile.

**Package present does not mean service enabled.**

---

## 9. GPU image and NVIDIA contract

Do not force an active NVIDIA kernel driver into every CPU worker.

Maintain a GPU-specific, versioned LayerSentry QCOW2 when GPU pools are enabled:

```text
LS-RKE2-<OS>-<RKE2>-GPU-<image-rev>.qcow2
```

The offline release may include, subject to licensing/redistribution rights:

- pinned NVIDIA driver bundle or customer-import mechanism;
- NVIDIA Container Toolkit;
- NVIDIA GPU Operator;
- device plugin;
- DCGM/DCGM exporter;
- GPU feature discovery/NFD dependencies;
- optional Network Operator/RDMA artifacts for certified profiles.

When the driver is preinstalled in the GPU QCOW2, configure GPU Operator not to replace it unless the exact release intentionally selects operator-managed driver lifecycle.

GPU worker pools use CloudStack GPU-capable service offerings/passthrough/vGPU mechanisms supported by the exact CloudStack/KVM/hardware profile.

**NVMe/RDMA storage and NVIDIA GPUDirect RDMA are different capabilities.** Do not advertise GPUDirect RDMA on generic CloudStack/KVM unless the exact GPU/NIC/driver/virtualization/storage combination is explicitly LayerSentry-certified.

---

## 10. CNI contract

The user selects a primary CNI during cluster creation because networking is required for cluster readiness.

Supported catalog candidates, subject to exact RKE2/CAPRKE2 release compatibility:

- Cilium — preferred advanced/security/eBPF profile;
- Canal — standard compatibility profile;
- Calico — BGP/network-policy-oriented profile;
- Flannel — simplified profile where appropriate;
- Multus — secondary CNI option, not a replacement primary CNI.

RKE2 air-gap artifacts may include core plus CNI-specific image archives. Keeping dormant CNI image archives in the QCOW2/offline release is acceptable; only the selected primary CNI is configured/running.

Primary CNI migration is not treated as a normal one-click package upgrade. It requires a certified migration procedure or cluster replacement/blue-green path.

---

## 11. Multi-storage cluster model

A LayerSentry K8s/Data Services cluster may have **multiple simultaneous storage profiles**.

Examples:

- CloudStack per-node data disk;
- CloudStack CSI block storage;
- CloudStack Shared FileSystem/NFS;
- upstream NFS CSI on an existing NFS server/CloudStack SharedFS;
- NetApp/Dell/HPE/Hitachi/Pure/other certified OEM CSI;
- NFS/iSCSI/NVMe-TCP;
- advanced NVMe/RDMA where the complete hardware/virtualization/driver path is certified;
- local NVMe/local-PV profile for explicitly node-local workloads.

The GUI must not force one cluster-wide storage choice when several StorageClasses/profiles can coexist.

### Storage ownership types

1. **Node-attached CloudStack data disk** — VM/node resource; CloudStack API owns create/attach/resize. Not a portable Kubernetes PVC unless separately modeled.
2. **CloudStack CSI block** — Kubernetes PVC/CSI resource; CSI owns backend lifecycle.
3. **CloudStack Shared FileSystem** — native CloudStack managed NFS/RWX source; Kubernetes may consume it as static NFS PV or via NFS CSI.
4. **OEM CSI block/file** — Kubernetes/OEM driver owns provisioning according to the exact array/driver profile.
5. **Advanced shared block** — only if an OEM/cluster filesystem explicitly supports multi-node writers. Never fake this with ordinary ext4/XFS on one raw LUN mounted read-write by many nodes.

### Critical shared-storage rule

Do **not** interpret CloudStack Disk Offering `shared` storage type as guest multi-attach. Normal CloudStack block data volumes are not assumed to be one raw block device concurrently writable by every RKE2 VM.

For a general multi-node read/write filesystem use:

```text
CloudStack Shared FileSystem -> NFS -> RWX pods/nodes
```

or a certified OEM file/CSI solution.

### Storage profile states

Catalog artifacts are:

- `AVAILABLE` — present locally and compatible enough to present;
- `ENABLED` — selected desired state;
- `READY` — reconciler/provider reports successful healthy installation and LayerSentry validation checks pass.

Do not call all bundled CSI drivers “installed but disabled”. Keep unselected Kubernetes drivers uninstalled.

---

## 12. StorageHostProfile activation

The QCOW2 contains generic clients, while the selected StorageProfile activates only what is required.

Example iSCSI/multipath profile:

```text
select OEM iSCSI
 -> validate node image/tools
 -> configure initiator
 -> enable required service
 -> apply vendor-qualified multipath policy
 -> validate paths/device behavior
 -> Flux installs selected CSI
 -> create backend/StorageClass/snapshot classes
 -> functional PVC test
 -> READY
```

Example NVMe/TCP profile:

```text
select OEM NVMe/TCP
 -> validate NIC/routing/MTU
 -> validate nvme-cli/module
 -> install selected CSI
 -> functional attach/mount/failover test
```

NVMe/RDMA requires explicit RDMA NIC presentation, KVM/SR-IOV/passthrough support, RDMA network and OEM CSI/storage validation. It is an Advanced/Certified-only option until the exact profile passes E2E tests.

---

## 13. CloudStack disk resize and CSI resize ownership

Use one owner per resource.

### Node-owned CloudStack volume

LayerSentry may use native CloudStack volume resize APIs, then perform the necessary guest rescan/filesystem expansion through a controlled operation.

### CSI-managed PVC

Resize the Kubernetes PVC and allow the selected CSI to resize the backend. Do not independently enlarge the CloudStack/OEM volume behind Kubernetes and then pretend Kubernetes has reconciled the change.

### Root disk

Prefer a new MachineTemplate/QCOW2/profile and CAPI rolling replacement when the standard root-disk layout changes. In-place root-disk resize is an exception requiring an explicit lifecycle reason and validation.

### CloudStack CSI project warning

Do not enable automatic PVC expansion for project-owned CloudStack CSI volumes until the exact selected driver build has passed project-aware expansion and idempotency tests. Any known upstream issue must be fixed/qualified before certification.

---

## 14. DBaaS storage policy

DBaaS production data must use a LayerSentry-certified Kubernetes storage path, not an arbitrary node-attached `/dev/vdX` disk.

Default DB profile:

```text
DB Operator
 -> PVC
 -> certified CSI
 -> NVMe-qualified StorageClass/tier
```

CloudStack storage tags/disk offerings/provider policy are used to prevent silent fallback from the required NVMe tier.

If capacity cannot satisfy the required DB storage tier, provisioning fails with a clear preflight error rather than silently moving to slower storage.

CloudStack SharedFS/NFS is available for workloads that genuinely need RWX, but it is not the default primary data path for PostgreSQL/MySQL/MongoDB/Kafka without workload-specific validation.

---

## 15. L4/L7/VIP/WAF ownership model

LayerSentry separates infrastructure/L4 from application/L7.

### CloudStack owns

- public/private IP inventory/allocation according to supported network topology;
- native CloudStack L4 load-balancer rules;
- firewall/ACL/NAT/VPC infrastructure as supported;
- internal LB where the exact network offering/topology supports it.

### Kubernetes owns

- Gateway API resources;
- HTTP/gRPC/TLS/TCP route intent according to the selected Gateway implementation;
- application routing policy;
- in-cluster service/endpoints.

### OEM ADC/WAF owns

- vendor virtual server/VIP when the hardware ADC is the selected frontend authority;
- WAF/bot/DoS/TLS/application-security policy supported by the vendor integration.

Do not label native CloudStack L4 load balancing as an AWS-style ALB.

---

## 16. Frontend/VIP abstraction and multi-VIP contract

Introduce a LayerSentry **Frontend** abstraction.

One application/backend may have many Frontends:

```text
Application Backend
  -> Frontend: Public L4 VIP
  -> Frontend: Private L4 VIP
  -> Frontend: Public L7 VIP
  -> Frontend: WAF VIP
  -> Frontend: Partner VIP
  -> Frontend: Management VIP
```

**One externally managed VIP = one LayerSentry Frontend lifecycle object.**

Each Frontend records:

- owner/tenant/project;
- provider;
- scope public/private;
- protocol/listeners;
- VIP reservation/selection;
- backend mapping;
- source CIDRs;
- TLS/certificate reference;
- WAF/policy reference when applicable;
- DNS intent;
- health state;
- retain/release behavior;
- audit/operation state.

A cluster may have many VIPs. A service/application may have several VIPs. Do not depend on one Kubernetes `Service` being portable across multiple CloudStack VIPs; create separate Service/Gateway/vendor frontend objects when deterministic ownership requires it.

One shared L7 Gateway VIP may serve multiple hostnames/services when policy permits.

RKE2 cluster control-plane VIP(s) are distinct from application VIPs and must provide the exact control-plane/supervisor endpoints required by the selected CAPRKE2/RKE2 release.

---

## 17. Exposure profiles — simple GUI

Normal users choose a small profile rather than raw CloudStack/Kubernetes objects:

```text
Network Exposure

Access:
  Private | Public

Type:
  Private Endpoint
  L4 Network Load Balancer
  L7 Application Load Balancer
  L7 + WAF

VIP:
  Automatic
  Select Existing
  Reserved/Specific (when allowed)

Provider:
  Automatic
  CloudStack
  LayerSentry Gateway
  Certified Hardware ADC/WAF
```

Advanced mode may expose provider, health algorithm, persistence, source CIDR, listener, TLS, Gateway class, WAF policy and provider-specific fields.

Feature choices are dynamically gated by CloudStack network offering/provider capability, IP availability, configured Gateway/WAF provider, role/RBAC, entitlement and compatibility.

Database wire protocols default to L4/private exposure. Do not place an HTTP WAF in front of PostgreSQL/MySQL/Redis/Kafka wire protocols merely because a WAF option exists.

Kafka exposure requires protocol-aware handling and may require bootstrap plus per-broker addresses depending on the exact Strimzi listener mode.

---

## 18. Hardware ADC/WAF integration

Use vendor-native Kubernetes/controller/API integration, not CloudStack-core patches.

Initial certification priority:

1. F5 BIG-IP/CIS or current F5 Gateway-compatible integration;
2. Radware Alteon/Kubernetes connector path;
3. Imperva/other OEM provider only after exact supported API/air-gap product validation.

LayerSentry provider contract should conceptually support:

```text
validateProvider()
reserveOrValidateVIP()
createFrontend()
configurePoolOrRoute()
configureTLS()
configureWAFPolicy()
health()
update()
delete()
```

If hardware ADC/WAF is the selected VIP authority, avoid an unnecessary extra CloudStack LB hop unless network architecture requires it.

Commercial images/software are not bundled without redistribution rights. The offline release may contain a LayerSentry adapter and customer/OEM import workflow.

---

## 19. CloudStack CCM and native API contract

Use CloudStack native API directly for discovery, reservation, infrastructure preflight and resources outside CAPC Machine ownership.

Use the Apache CloudStack Kubernetes Provider/CCM where it correctly reconciles Kubernetes L4 `LoadBalancer` Services to CloudStack.

LayerSentry should not create a competing CCM.

Because Kubernetes `spec.loadBalancerIP` has deprecated semantics, LayerSentry must track upstream CloudStack Provider evolution and prefer a future provider-specific annotation/`loadBalancerClass` or other supported mechanism when available. Until then, an exact qualified provider version may use its documented current mechanism.

---

## 20. Internal package lifecycle — central Flux

LayerSentry uses central Flux on the management cluster as the internal package reconciler.

Reasons:

- HelmRelease lifecycle;
- remote-cluster kubeconfig support;
- natural composition with CAPI-created `<cluster>-kubeconfig` Secrets;
- OCI source support;
- dependency ordering;
- drift reconciliation;
- install/upgrade remediation;
- no mandatory tenant-facing GitOps UI.

LayerSentry may use source-controller, helm-controller and only the additional Flux controllers that are justified by the package contract.

Tenant/customer GitOps remains a separate optional choice:

- Argo CD;
- Flux CD;
- none.

A customer uninstalling their own GitOps tooling must never break LayerSentry internal package management.

Do not add Rancher/Fleet/Crossplane/AWX/CAAPH/GitLab/Gitea as mandatory platform dependencies without a new research decision showing a clear production advantage.

---

## 21. Package catalog and late installation

Everything permitted by a release may be **available locally without being installed in every cluster**.

Catalog categories include:

### Core

- CoreDNS/RKE2 packaged components;
- Helm tooling where required;
- metrics-server;
- CloudStack CCM;
- CSI snapshot components where selected.

### Certificate

- cert-manager;
- private/enterprise CA adapters when certified.

### GitOps

- Argo CD;
- Flux CD.

### Security

- Trivy/Trivy Operator;
- kube-linter;
- Falco;
- Tracee;
- Cilium features;
- NeuVector;
- Kyverno;
- optional Gatekeeper;
- signing/SBOM policy tools such as Cosign/Notation where applicable.

### Observability

- Prometheus;
- Alertmanager;
- Grafana;
- Grafana Alloy;
- Loki;
- Tempo;
- OpenTelemetry Collector;
- kube-state-metrics;
- node exporter and approved Kubernetes metrics components.

### Operations

- Velero;
- Node Problem Detector;
- descheduler;
- KEDA;
- VPA;
- Prometheus Adapter;
- rollout/progressive-delivery tools when certified.

### Networking/security appliances

- Gateway implementations;
- NFS/CloudStack/OEM CSI packages;
- certified F5/Radware/other adapters.

Users can install an `AVAILABLE` package after cluster creation through the LayerSentry GUI. No ISO reinstall or cluster reinstall is required. The package controller performs compatibility/preflight checks, reconciles through Flux and reports exact progress/partial failure.

A package requiring a new host-level kernel/driver capability may require a new node image/MachineTemplate rollout; the GUI must show this before execution.

---

## 22. Offline artifact service and bundle model

Every LayerSentry installation has a platform-owned local artifact source that exists independently of tenant Harbor.

It may expose:

- OCI registry;
- Helm OCI;
- raw release files;
- RPM/DEB repositories;
- signatures/SBOM/provenance metadata.

Connected and air-gapped deployments consume the **same approved artifact digests**. Connected mode may mirror/download into the local service; air-gap mode imports signed media/bundles.

Tenant Harbor is APaaS and must not be a bootstrap dependency for the Kubernetes cluster that will run Harbor.

Air-gap validation is done behind deny-all Internet egress and includes install, scale, repair, node replacement, package install, backup/restore and upgrade of the exact release.

---

## 23. ISO #1 — LayerSentry K8s offline release

Conceptual artifact:

```text
layersentry-k8s-<release>.iso
```

Contains at least:

```text
release/
  manifest
  compatibility
  signatures
  checksums
  SBOM/provenance

capi/
capc/
caprke2/
rke2/
flux/

images/
  cpu-rke2.qcow2
  gpu-rke2.qcow2 when enabled

registry/
charts/

cni/
  cilium
  canal
  calico
  flannel
  multus

storage/
  cloudstack-csi
  nfs-csi
  certified-oem-adapters

networking/
  gateway implementations
  ADC/WAF adapters

security/
observability/
backup/
operations/

nvidia/ when licensed/approved
rpm/
deb/
licenses-notices/
```

The release builder must be reproducible enough to recreate the same source-defined contents, verify upstream checksums/signatures where available, scan dependencies/images, generate SBOM/provenance, sign the LayerSentry manifest/artifacts and fail closed on integrity mismatch.

---

## 24. ISO #2 — LayerSentry Data Services/APaaS offline release

Conceptual artifact:

```text
layersentry-data-services-<release>.iso
```

Contains only versions compatible with the required LayerSentry K8s platform release, including as applicable:

- LayerSentry-branded OpenEverest build/adapter;
- database operators and approved images;
- Redis/Valkey operator/provider and images;
- Strimzi and Kafka images;
- OpenBao;
- Harbor;
- backup/restore dependencies;
- dashboards/alerts/integration charts;
- DBaaS/APaaS package metadata;
- upgrade graphs;
- signatures/SBOM/provenance/licenses.

The Data Services release declares an explicit compatible LayerSentry K8s/platform range and fails closed outside it.

---

## 25. DBaaS cluster topology

Default dedicated LayerSentry Data Services production profile:

```text
3 x RKE2 control-plane/server/etcd
4 x DB worker
```

DB workers use:

- dedicated labels/taints;
- anti-affinity/topology spread;
- NVMe-certified storage only;
- workload quotas/PDBs/priority policies;
- database-specific monitoring/backup.

Production Kafka/APaaS should use separate worker pools where capacity/isolation warrants it. Small/lab profiles may share workers only with explicit resource warnings and non-production policy.

For regulated/large customers, separate Kubernetes clusters may be selected rather than forcing all Data Services into one cluster.

---

## 26. LayerSentry DBaaS and OpenEverest

OpenEverest is used as a database control component for supported engines only after exact-version qualification. It does not provision the underlying LayerSentry Kubernetes cluster.

LayerSentry DBaaS normal customer UI presents:

- PostgreSQL;
- MySQL/PXC;
- MongoDB;
- Redis;
- optional Valkey;
- future certified providers.

### Branding must survive upgrades

Customer-visible branding must remain LayerSentry after an OpenEverest upgrade.

Approved strategies, in preferred long-term order:

1. **LayerSentry-owned DBaaS UI/API facade** over stable OpenEverest APIs/operator semantics; upstream OpenEverest UI is not customer-facing.
2. For early implementation, build a pinned LayerSentry OpenEverest image from the exact upstream tag with a small automated branding overlay and set Helm values to the LayerSentry image.

Branding overlay pipeline must automatically apply/test:

- LayerSentry name/logo;
- theme/colors;
- customer navigation/links;
- forbidden upstream customer-facing branding checks;
- legal LICENSE/NOTICE attribution preservation.

If an upstream frontend change breaks the branding patch, the build fails. It must never silently fall back to an upstream-branded image.

### OpenEverest air-gap rule

Do not claim upstream OpenEverest air-gap support unless current official upstream documentation explicitly supports the exact release. LayerSentry may engineer an offline distribution by mirroring images/charts/dependencies, disabling/redirecting external telemetry/version calls and proving deny-all-egress operation, but that becomes a **LayerSentry-certified profile** only after E2E tests.

### Redis/Valkey

Do not force Redis into a stable OpenEverest engine model if it is not supported there. Present one LayerSentry DBaaS catalog and route supported engines to the appropriate provider/operator adapter. Re-evaluate a future OpenEverest provider SDK only after its production maturity is proven.

---

## 27. DBaaS GUI contract

The customer should not need to know Helm, CRDs, StatefulSets, operators or StorageClass internals.

Example flow:

```text
Data Services -> DBaaS -> Create Database

Engine
Version
Topology/HA
CPU/RAM profile
Storage size
Storage tier = NVMe certified
Auto-grow policy when certified
Backup/PITR
Maintenance window
Connectivity/exposure
Monitoring
Review/Preflight
Deploy
```

Connectivity defaults:

- private endpoint;
- L4 protocol-specific VIP/service;
- TLS according to engine/operator support;
- explicit allowed CIDRs;
- public endpoint only under policy/advanced scope.

HTTP WAF is for the DBaaS portal/API, not for the PostgreSQL/MySQL wire protocol.

---

## 28. DB backup, PITR and upgrades

Database lifecycle is distinct from Kubernetes lifecycle.

Do not combine all of these into one blind transaction:

- Kubernetes/RKE2 minor upgrade;
- CSI major upgrade;
- database operator major upgrade;
- database engine major upgrade.

Use separate compatibility-gated maintenance workflows.

DBaaS production certification requires engine-specific:

- backup;
- restore;
- PITR where offered;
- node failure/failover;
- storage interruption;
- worker replacement;
- operator upgrade;
- engine upgrade;
- rollback/recovery classification;
- data-integrity validation.

The global DR context remains authoritative for cross-site/fencing/DR orchestration. This module must integrate with it rather than create a second DR framework.

---

## 29. APaaS

Initial LayerSentry APaaS services:

- **OpenBao** — secrets platform;
- **Harbor** — tenant container registry.

### OpenBao production profile

Use an exact certified HA topology, typically multiple replicas with integrated Raft storage, TLS, anti-affinity, persistent storage, backup/snapshot and restricted NetworkPolicy. Do not present standalone/development mode as production HA.

### Harbor production profile

Use an exact HA profile appropriate to the certified release, including external/HA dependencies and shared/object persistence where required. If LayerSentry DBaaS provides PostgreSQL/Redis to Harbor, the dependency graph must be explicit and resilient; Harbor must not bootstrap the platform registry used to create its own Kubernetes cluster.

---

## 30. Streaming/Kafka

Use Strimzi for Kafka lifecycle rather than building a Kafka operator.

LayerSentry Streaming GUI asks for business/operational intent:

- Kafka version from certified catalog;
- broker/node count;
- CPU/RAM profile;
- storage profile;
- replication/retention policy;
- TLS/authentication;
- exposure mode;
- monitoring;
- maintenance window.

Production Kafka uses dedicated workers where required by performance/failure isolation.

External LoadBalancer listener modes may require a bootstrap endpoint and per-broker endpoints. LayerSentry must calculate/address the exact VIP requirement rather than pretending one generic ALB always works.

Strimzi/operator upgrades and Kafka broker upgrades follow explicit supported upgrade graphs and workload-aware validation.

---

## 31. Simple GUI-only customer experience

The normal user experience is service-oriented, not infrastructure-object-oriented.

Top-level navigation may include:

```text
Kubernetes
  Clusters
  Worker Pools
  Storage
  Packages
  Gateways

Data Services
  DBaaS
  Redis/Valkey
  Streaming/Kafka

APaaS
  OpenBao
  Harbor

Networking
  VIPs
  Frontends
  Gateways
  Load Balancers
  WAF Policies
  Certificates

Operations
  Backups
  Upgrades
  Monitoring
```

The same reusable components are used across modules:

- Ownership/Site selector;
- compute/node-pool profile;
- StorageProfile selector;
- Exposure/Frontend selector;
- package catalog;
- backup/maintenance policy;
- Review/Preflight/Deploy;
- async operation timeline.

No YAML, manual SSH, raw SAN credentials, raw IQN/LUN handling or manual RKE2 token entry is required for normal workflows.

Advanced mode may expose validated low-level choices to authorized Platform Administrators.

---

## 32. LayerSentry K8s create wizard

Normal sections:

1. General — cluster name, project/account, Site, profile, certified RKE2 release.
2. Control plane — production default 3 nodes; service/placement profile.
3. Worker pools — general/DB/Kafka/GPU/custom.
4. Network — primary CNI, optional Multus, CIDRs, API endpoint/VIP, exposure readiness.
5. Storage — zero or more StorageProfiles, per-node disks, CSI/file providers, default StorageClass.
6. Packages — curated category checkboxes/profiles.
7. Security — hardened profile, admission/runtime/image policy.
8. Observability — monitoring/logging/tracing profile.
9. Connectivity — connected/air-gap.
10. Review/Preflight — exact resolved versions, IPs, provider requirements, licenses, compatibility and resource plan.

Deployment is one GUI action backed by a durable resumable workflow and controller reconciliation.

---

## 33. Post-deployment package/storage/node-pool UX

After creation the user can:

- add/remove/scale worker pools through CAPI policy;
- add a GPU pool;
- add a StorageProfile;
- add CloudStack per-node disks through a controlled node-pool operation;
- install an available package;
- enable a Gateway/WAF integration;
- request new Frontends/VIPs;
- schedule upgrades;
- perform backups/restore according to certified features.

No ISO reinstall is required for normal package/CSI/operator additions present in the local catalog.

If a selected later feature requires a new kernel/host driver, LayerSentry proposes the required node-image rollout before enabling it.

---

## 34. Durable provisioning workflow contract

Composite GUI operations use a durable state machine/saga. Do not perform 40 untracked shell commands inside one HTTP request.

Conceptual cluster states:

```text
REQUESTED
VALIDATING
RESOLVING_INFRA
RESERVING_VIPS
CREATING_CAPI_OBJECTS
CONTROL_PLANE_BOOTSTRAP
CONTROL_PLANE_READY
WORKER_POOLS_READY
CNI_READY
CCM_READY
STORAGE_HOST_PREFLIGHT
CSI_READY
BASE_PACKAGES_READY
OPTIONAL_PACKAGES_READY
EXPOSURE_READY
HEALTH_CHECK
READY

PARTIAL
FAILED_RETRYABLE
FAILED
DELETING
```

Persist operation/resource IDs, async CloudStack job IDs where used, retries, last error and compensation/recovery state.

A timeout of a mutating operation is `UNKNOWN` until the authoritative resource/job/controller state is inspected.

---

## 35. Capability discovery and preflight

Never show a feature merely because code exists.

Preflight dynamically checks as applicable:

- caller/RBAC/tenant scope;
- CloudStack Site/network/VPC/network offering;
- public/private IP availability;
- LB/InternalLB service availability;
- compute/service offerings;
- disk offerings/storage tags;
- template/image availability;
- GPU offering/hardware capability;
- storage provider/CSI profile health;
- required host tools/image profile;
- CNI/Gateway/package compatibility;
- OEM connector entitlement/readiness;
- required air-gap artifacts present locally;
- Kubernetes/RKE2/CAPI/CAPC/CAPRKE2 release tuple.

Invalid combinations are hidden or disabled with an actionable reason.

---

## 36. Security and tenancy

CloudStack RBAC remains authoritative for CloudStack resources. LayerSentry's privileged module services additionally authorize every composite action against the exact tenant/project/resource.

Kubernetes security baseline includes as appropriate:

- namespaces/tenant isolation;
- RBAC;
- default-deny NetworkPolicy in hardened profiles;
- Pod Security Admission;
- quotas/LimitRanges;
- service-account policy;
- audit logging;
- secrets management;
- admission policy;
- image/signature/SBOM policy where enabled.

Never expose CloudStack admin/API credentials to browser clients or tenant pods. CCM/CSI/provider credentials are least-privilege, scoped and stored through approved secret mechanisms.

External provider endpoints are SSRF/TLS trust boundaries and follow `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`.

---

## 37. Observability and supportability

LayerSentry should offer a coherent observability profile rather than blindly installing overlapping agents.

Candidate standard stack:

- Prometheus;
- Alertmanager;
- Grafana;
- Alloy;
- Loki;
- Tempo;
- OpenTelemetry Collector;
- kube-state-metrics;
- node exporter and approved metrics components.

Support diagnostics must work offline and include sanitized:

- release/compatibility manifest;
- CAPI/CAPC/CAPRKE2 conditions;
- RKE2/server/agent health;
- CNI/CCM/CSI state;
- node storage tools/path/multipath/NVMe/NFS diagnostics;
- package HelmRelease/Flux conditions;
- Gateway/VIP/frontend state;
- DB operator/application state;
- recent async/controller failures.

Do not require arbitrary Internet package installation during an incident just to collect baseline evidence.

---

## 38. Upgrade model after three months and beyond

Separate lifecycle classes.

### Package-only update

Examples: Prometheus, Loki, Falco, Trivy, OpenBao chart, Harbor chart, most operator/CSI controller patch updates.

- import/sync signed package bundle;
- update compatibility/release metadata;
- Flux reconciles selected target version;
- health/remediation/rollback rules apply;
- no QCOW2 rebuild unless host dependencies changed.

### Host/RKE2/kernel update

- build a new signed QCOW2;
- qualify it;
- new CloudStack template;
- new CAPI MachineTemplate/topology reference;
- staged CAPI rollout;
- drain/replace/validate nodes.

### NVIDIA kernel driver update

Normally requires a new GPU QCOW2 or a specifically certified operator-managed driver workflow. Do not mutate GPU hosts ad hoc.

### CNI major/migration

Not a normal Helm click. Use a certified migration or blue/green cluster strategy.

### CSI major/migration

Requires storage-provider data-safety validation, attach/detach/snapshot/resize tests and rollback/recovery plan.

### Database engine/operator update

Separate maintenance workflow from Kubernetes/CSI upgrades.

### Release rings

Use internal/nightly -> dev -> non-production -> production canary -> production fleet rollout. Stop on defined health/data/storage regression signals.

---

## 39. Autoscaling and remediation

CAPI/Cluster Autoscaler handles worker-pool scaling for supported profiles.

Scale-down/remediation for stateful pools is conservative and storage-aware:

- cordon/drain;
- PDB validation;
- volume detach/reattach validation;
- DB/Kafka operator health;
- only then Machine deletion.

DB worker automatic scale-down may remain disabled until the exact operator/storage combination is certified.

MachineHealthCheck/remediation is not enabled blindly on stateful pools. Prove volume/PVC safety first.

---

## 40. Production storage/data-safety certification gates

For every CSI/storage profile test at least:

- provision;
- attach;
- mount;
- detach;
- delete;
- snapshot;
- restore;
- clone where offered;
- expansion where offered;
- filesystem resize;
- node reboot;
- worker replacement;
- host failure;
- storage controller/path failure;
- multipath failover where applicable;
- CSI controller restart;
- Kubernetes/RKE2 upgrade;
- CSI upgrade/rollback classification;
- tenant/project scoping;
- accidental-delete protection.

For CAPC + CSI specifically, attach a workload PVC, delete/replace the CAPI Machine and prove the workload PVC is **not destroyed** by Machine lifecycle cleanup.

For CloudStack SharedFS/NFS test simultaneous RWX, server fail/recovery, network interruption, remount behavior, capacity/resize behavior, NFS CSI dynamic subdirectory behavior and quota semantics before advertising per-PVC hard quota.

---

## 41. Production cluster certification gates

Before a LayerSentry K8s release/profile is `PRODUCTION_CERTIFIED`, prove the exact artifact/profile for:

- fresh fully offline cluster create;
- automatic 3-control-plane formation;
- automatic worker join;
- scale up/down;
- worker-pool add/remove;
- control-plane replacement;
- worker replacement;
- KVM host failure;
- CloudStack management interruption during reconciliation;
- CAPI/management-controller restart during provisioning;
- API/supervisor VIP failover;
- CNI failure/recovery;
- CCM/L4 LB lifecycle;
- selected CSI full data-safety matrix;
- package late install/uninstall/upgrade;
- Flux controller restart/reconciliation;
- certificate lifecycle;
- backup/restore;
- supported N-1 -> N RKE2/Kubernetes upgrade;
- interrupted upgrade/resume;
- air-gap scale/repair/upgrade with deny-all external egress;
- browser/UI/RBAC/negative tests;
- support bundle/evidence.

DBaaS/APaaS/Streaming add their own workload-specific gates and are not automatically certified merely because the base cluster is certified.

---

## 42. DBaaS/APaaS/Streaming certification gates

### DBaaS

- engine/operator compatibility;
- HA/failover;
- backup and restore;
- PITR where offered;
- worker replacement;
- storage failure/path failover;
- PVC expansion when offered;
- TLS/RBAC/network policy;
- upgrade path;
- data integrity under failure;
- OpenEverest/LayerSentry branding persists after upgrade;
- deny-all-egress offline proof for every LayerSentry offline claim.

### Kafka/Strimzi

- broker/node loss;
- worker replacement;
- storage failure;
- rolling upgrade;
- listener/VIP reconciliation;
- partition/replication health;
- monitoring/alerting;
- backup/recovery where offered.

### OpenBao

- quorum/HA failure;
- seal/unseal/key-management procedure;
- persistent storage recovery;
- snapshot/restore;
- upgrade/rollback classification;
- network/TLS/RBAC.

### Harbor

- HA dependencies;
- registry persistence;
- external DB/Redis dependency behavior where selected;
- backup/restore;
- scanning/signing integration;
- upgrade/rollback;
- no circular dependency on tenant Harbor for platform bootstrap.

---

## 43. Production readiness and three-day expectation

Do not label this full platform `PRODUCTION_CERTIFIED` merely because Codex can generate the source/configuration/ISO quickly.

A short engineering sprint may produce a strong integrated POC/release candidate including:

- QCOW2 builder;
- offline bundle builder;
- CAPI/CAPC/CAPRKE2 manifests;
- RKE2 air-gap bootstrap;
- central Flux;
- package catalog;
- GUI profile skeleton;
- OpenEverest branding build;
- DBaaS/APaaS/Strimzi package definitions;
- selected storage/network adapters.

Production certification remains constrained by real CloudStack `4.22.1.1` integration, destructive data tests, OEM hardware/storage availability, air-gap tests, security tests, upgrade/rollback, failure injection and soak/performance evidence.

Use status labels honestly.

---

## 44. Licensing and redistribution

Before including third-party binaries/images in LayerSentry release media:

- review license/NOTICE obligations;
- verify redistribution rights;
- retain required attribution;
- do not bundle commercial OEM software without the applicable agreement;
- provide customer/OEM import mechanism where redistribution is not permitted;
- pin exact versions/digests and scan them through the release pipeline.

Open-source rebranding does not remove legal attribution requirements.

---

## 45. Implementation ownership and non-impact boundary

This module should be implemented in LayerSentry-specific files/services/controllers and isolated UI modules wherever practical.

Do **not** use this module as permission to refactor unrelated:

- VM Quick Provision;
- CloudStack B&R/DR architecture;
- CloudStack management-server HA;
- CloudStack DB topology;
- object-storage workflows;
- appliance-lockdown policy;
- release-signing policy;
- general KVM host lifecycle;
- existing RBAC semantics.

Shared components may be extended only when necessary and regression-tested for existing VM/Storage/Network/DR behavior.

The module's new navigation/routes must be feature-gated so unfinished/uncertified backends are not falsely presented as ready.

---

## 46. Required Codex workstream behavior

A Kubernetes/DBaaS/APaaS workstream must:

1. inspect the actual current LayerSentry integration branch before editing;
2. read this document in addition to global contexts;
3. research exact current versions/source/issues before changing the architecture tuple;
4. work in an isolated branch/worktree;
5. preserve CloudStack core by default;
6. maintain a compatibility/release manifest rather than scattering version conditionals;
7. add tests at the correct layer;
8. use the `adaptgurus/cozystack` runner/live path for runtime claims when applicable;
9. record exact artifacts/evidence in the progress ledger only after actual tests;
10. never self-promote a source change to production-ready status;
11. update this file only when the stable module architecture/policy changes.

---

## 47. Source families to revalidate for major module changes

At minimum, as applicable:

### CloudStack

- exact `apache/cloudstack` `4.22.1.1` source;
- CloudStack 4.22.1.1 admin/API/release documentation;
- CloudStack Kubernetes Service and ExternalManaged behavior where used for visibility/integration;
- Shared FileSystem source/docs;
- LB/InternalLB/public-IP/VPC/network-offering behavior;
- async job semantics;
- CloudStack Kubernetes Provider/CCM;
- CloudStack CSI driver issue/PR history.

### Kubernetes lifecycle

- Cluster API version support;
- CAPC compatibility/issues/PRs;
- CAPRKE2 releases/APIs;
- RKE2 networking, air-gap, HA and upgrade docs.

### Package/GitOps

- Flux source/helm controller APIs and remote CAPI cluster behavior;
- Helm/OCI behavior;
- selected package/operator release notes.

### Data services

- OpenEverest stable documentation/API/support matrix/upgrade path;
- Percona operator support matrices;
- Redis/Valkey operator/provider;
- Strimzi release/support matrix;
- OpenBao production Helm/HA guidance;
- Harbor HA guidance.

### Storage/GPU/OEM

- selected OEM CSI/operator docs and issue history;
- host prerequisite/multipath/FC/iSCSI/NVMe requirements;
- NVIDIA driver/GPU Operator/Network Operator docs and licensing;
- exact KVM/SR-IOV/passthrough hardware support.

Community evidence is diagnostic input; exact source/docs plus LayerSentry tests determine certification.

---

## 48. Definition of success for this module

The engineering target is:

> A customer can provision and operate LayerSentry K8s, DBaaS, APaaS and Streaming entirely through a simple role-aware GUI, while CloudStack remains the KVM/IaaS authority, CAPI/CAPC owns cluster Machines, CAPRKE2 owns RKE2 lifecycle, Flux owns package reconciliation, operators own application-specific lifecycle, multiple storage/VIP/provider choices remain composable, offline/connected releases consume the same approved artifacts, upgrades are deterministic and data-safe, and no capability is called production-ready until the exact CloudStack 4.22.1.1 release/profile has passed its destructive functional/security/storage/upgrade/recovery evidence gates.

The best implementation is the smallest supportable overlay that preserves upstream authorities, avoids duplicate controllers, survives upgrade/recovery, keeps customer UX simple, and remains technically honest about what has and has not been certified.

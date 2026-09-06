# LayerSentry K8s / DBaaS / APaaS — Validated Architecture Addendum

**Status:** `DESIGN_DEFINED` / mandatory companion to the Kubernetes specialist master context  
**Scope:** only LayerSentry-managed Kubernetes, DBaaS, APaaS, Streaming and their cluster storage/network/package lifecycle  
**Cloud baseline:** Apache CloudStack `4.22.1.1` + KVM  
**Authority:** extends `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`; it does not replace unrelated global LayerSentry rules

This addendum exists because exact upstream source validation found several integration details that are materially important for production and were too implicit in the original specialist context. The original architecture remains selected, but the rules below are mandatory and take precedence where they are more specific.

Do not infer production support from the existence of a release, API field, Helm chart or GitHub example. Exact LayerSentry release tuples are promoted only after the E0 compatibility matrix and required live/destructive evidence pass.

---

## 1. CAPI / CAPC / CAPRKE2 compatibility is a release tuple, not independent component selection

The architecture remains:

```text
LayerSentry
  -> Cluster API
      -> CAPC -> CloudStack 4.22.1.1 / KVM
      -> CAPRKE2 -> RKE2
```

However, **CAPI, CAPC and CAPRKE2 cannot be selected independently**. A LayerSentry release pins one tested tuple.

### Current released compatibility lanes identified during 2026-09-06 validation

These values are current evidence, not permanent product locks. Revalidate before every release.

#### Lane A — released legacy-contract overlap

```text
CAPI       1.9.6
CAPC       0.6.1
CAPRKE2    0.15.0
Kubernetes workload ceiling from the CAPI 1.9 support matrix: 1.32
```

Why it matters:

- CAPC `v0.6.1` is built against CAPI `v1.9.6`;
- CAPRKE2 `v0.15.0` is built against CAPI `v1.9.5` / test dependency `v1.9.6`;
- this proves that a fully released CAPC + CAPRKE2 overlap exists.

Why it is **not** the intended LayerSentry production lane:

- the LayerSentry target is a current RKE2/Kubernetes line such as Kubernetes `1.36`, while CAPI `1.9` does not provide that workload-version support.

Use this lane only for compatibility/reference testing or an explicitly supported older Kubernetes profile. Do not downgrade the LayerSentry target merely to avoid modernizing/qualifying CAPC.

#### Lane B — released modern CAPI/RKE2 with temporary v1beta1 infrastructure-provider bridge

First modern E0 qualification candidate:

```text
CAPI       1.13.5
CAPRKE2    0.25.2
CAPC       0.6.1
RKE2       1.36.4+rke2r1 candidate
CloudStack 4.22.1.1
```

Important nuance:

- CAPRKE2 `v0.25.2` is built against CAPI `v1.13.5`;
- CAPC `v0.6.1` still implements the older CAPI infrastructure contract;
- current CAPI v1beta2 contract documentation provides **temporary backward compatibility with v1beta1 infrastructure providers**.

Therefore this combination is **not declared incompatible merely because CAPC has not yet migrated to v1beta2**. It is a legitimate test candidate.

It is also not automatically supported. LayerSentry must prove:

- provider startup/contract compatibility;
- Cluster/CloudStackCluster/Machine reconciliation;
- ClusterClass/topology operations used by LayerSentry;
- create/scale/delete/upgrade/remediation;
- CloudStack 4.22.1.1 behavior;
- CAPRKE2 bootstrap and endpoint behavior;
- data safety.

The CAPI v1beta1 compatibility bridge is temporary/deprecated. It cannot be the permanent LayerSentry strategy.

#### Lane C — modern CAPI contract / future-proof CAPC lane

```text
CAPI       1.13.x
CAPRKE2    0.25.2-compatible
CAPC       v1beta2-contract build derived from upstream PR #493 or later released equivalent
RKE2       1.36.x candidate
CloudStack 4.22.1.1
```

Upstream CAPC PR `#493` upgrades CAPC to CAPI `1.13.2`, implements the v1beta2 infrastructure contract and promotes CAPC provider API storage/hub behavior. During this validation it remained **open and unmerged**.

Rules:

- do not call PR #493 an upstream stable release;
- if Lane B fails because of contract limitations, LayerSentry may build a pinned downstream CAPC from a reviewed/rebased v1beta2-contract commit;
- downstream CAPC must have exact source commit, patch manifest, SBOM, image digest, test evidence and upstream-delta record;
- prefer returning to an upstream released CAPC as soon as the required fixes/contract land and pass regression tests.

### Production selection rule

**No production tuple is selected by this document.** E0 must test Lane B first because it uses released CAPC/CAPRKE2 artifacts, compare it to Lane C, and record the winning exact tuple in the release manifest/evidence.

---

## 2. RKE2 control-plane endpoint requires both 6443 and 9345

CAPRKE2 currently generates RKE2 join/bootstrap server URLs on TCP `9345`. Kubernetes API traffic uses TCP `6443`.

Current CAPC isolated-network endpoint code creates the CloudStack control-plane LoadBalancer rule for the Kubernetes API path (`6443`) and tracks one load-balancer rule ID. It does **not by itself prove an RKE2 `9345` rule is created**.

This is a hard integration gate.

### Required endpoint contract

A LayerSentry-managed RKE2 control-plane endpoint must provide stable HA reachability for at least:

```text
VIP/FQDN:6443 -> all healthy RKE2 server/control-plane nodes:6443
VIP/FQDN:9345 -> all healthy RKE2 server/control-plane nodes:9345
```

The exact RKE2/CAPRKE2 release may add other requirements; revalidate before release.

### Ownership rule

Use **one endpoint authority**. Approved patterns after qualification are:

1. **LayerSentry-qualified CAPC endpoint enhancement** that owns the CloudStack VIP and both LB rules, including assignment/deletion/reconcile semantics; or
2. a validated private/internal/hardware HA endpoint provider that owns both ports and is declared in the cluster profile.

Do not have CAPC own one rule while an unrelated controller silently owns another rule on the same lifecycle without an explicit ownership/reconciliation contract.

A kube-vip example in CAPC is not proof of CAPRKE2 production compatibility; it must be tested with RKE2 and the actual LayerSentry network topology before use.

The GUI may still expose one simple field such as **Kubernetes API VIP**; LayerSentry internally provisions all required control-plane ports.

---

## 3. CAPC Machine deletion / attached DATADISK behavior is a hard data-safety blocker

Upstream CAPC issue `#389` documented potential data loss when a CAPI Machine is destroyed while a CloudStack CSI PVC/data volume is attached.

Current CAPC source validation still shows this relevant behavior:

```text
DestroyVMInstance
  -> list all volumes attached to the VM with type DATADISK
  -> pass the resulting volume IDs to destroyVirtualMachine
```

That means **closing the historical issue as stale/not-planned is not evidence that the risk disappeared**.

### LayerSentry mandatory rule

Before any stateful/DBaaS production profile uses CAPC Machine replacement or scale-down, LayerSentry must ensure CAPC deletion can distinguish:

- CAPC-owned ephemeral/deploy-time node disk(s); from
- Kubernetes CSI workload volumes attached later; from
- LayerSentry-managed node disks with an explicit retain/delete policy.

A safe implementation should use explicit ownership metadata/tags and delete only volumes owned by the Machine lifecycle. Unowned/CSI workload volumes must not be passed for destruction merely because they are attached when the VM is deleted.

Until that is fixed and destructively tested:

- CAPC + stateful CSI Machine replacement is **BLOCKED for production certification**;
- automatic MachineHealthCheck remediation on stateful pools remains disabled;
- DB worker automatic scale-down remains disabled;
- no claim of data-safe immutable node rollout is permitted for the affected storage path.

Required destructive test:

1. create workload PVC and write identifiable data;
2. attach/mount on a CAPI worker;
3. replace/delete the CloudStackMachine;
4. prove the PVC/backend CloudStack volume still exists and data is intact;
5. prove it can attach/mount to the replacement node;
6. repeat during upgrade, scale-down and failure remediation.

---

## 4. Multiple per-node CloudStack disks require a NodeDisk ownership model

The product requirement allows users to attach multiple disks/storage types to a cluster. That remains valid, but **not all disk types are the same lifecycle**.

Current CAPC CloudStackMachine models a single deploy-time `DiskOffering`; it does not provide a generic list of arbitrary additional node data disks with independent retain/delete policies.

Therefore distinguish:

### A. Multiple Kubernetes persistent volumes

Fully valid design:

```text
Pod -> PVC -> StorageClass A -> CloudStack/OEM CSI
Pod -> PVC -> StorageClass B -> NFS CSI
Pod -> PVC -> StorageClass C -> OEM CSI
```

Several StorageProfiles/StorageClasses can coexist. This does not require CAPC to own the workload volumes.

### B. Node-owned CloudStack disks

For extra disks attached directly to each worker, LayerSentry needs an explicit **NodeDiskSet** (name may change during implementation) lifecycle contract containing at least:

- node-pool owner;
- CloudStack volume ID;
- disk offering/tier;
- size/IOPS;
- purpose (`scratch`, `container-data`, `cache`, other approved use);
- attach device/identity discovered after CloudStack attach;
- retain/delete policy;
- encryption policy;
- resize policy;
- replacement behavior;
- CAPI Machine relationship;
- CloudStack tags proving ownership.

No node disk is deleted merely because it was attached to a Machine at deletion time.

### Initial production policy

Until CAPC/NodeDiskSet ownership is fixed and tested:

- the single CAPC deploy-time node disk may be used only according to its certified semantics;
- additional node-attached disks are `PENDING`/advanced, not production-certified;
- durable application/database data uses certified CSI/PVC storage, not a node disk;
- scratch/cache disks may be introduced first because losing/recreating them is semantically safer.

---

## 5. CloudStack CSI v3.0.2 changes the project-scope assessment but not the certification gate

The CloudStack CSI project has released `cloudstack-csi-3.0.2`.

The release includes the merged project-scope client change that sets `cloudstack.WithProject(projectID)` as a default client option. This is relevant to the earlier project-owned volume lookup failure.

However, exact `v3.0.2` source validation also shows that `ExpandVolume` still performs a resize request without first converging/idempotently returning when the requested size is already satisfied.

Therefore the correct LayerSentry statement is:

- do **not** claim that v3.0.2 definitely still has the original project `Count:0` problem;
- do **not** close the qualification gate merely because project defaults were added;
- test project-owned provision/attach/detach/snapshot/restore/resize on CloudStack `4.22.1.1`;
- test repeated/idempotent resize/reconcile calls;
- enable automatic PVC growth only after the exact selected CSI build passes.

CloudStack CSI project issue `apache/cloudstack#13634` remains useful failure evidence even when a newer driver may address part of its root cause.

---

## 6. RKE2/Kubernetes release target rule

Current validation found RKE2 `v1.36.4+rke2r1` as a published release and CAPI `1.13.x` supports Kubernetes `1.36` workload clusters.

This makes RKE2/Kubernetes `1.36.x` a reasonable **E0 candidate**, not an automatic production selection.

LayerSentry Certified still requires the complete tuple:

```text
CloudStack + CAPI + CAPC + CAPRKE2 + RKE2 + OS/QCOW2
+ CNI + CCM + CSI + Gateway + package/operator matrix
```

Production remains a curated/staged channel; do not expose upstream `latest` automatically.

---

## 7. OpenEverest current support boundary is explicit

Versioned OpenEverest `v1.16.2` documentation states:

- Kubernetes support: `1.33` through `1.36`;
- supported Percona operator lines for PXC, MongoDB and PostgreSQL;
- **air-gapped environments are not currently supported**.

Therefore the original LayerSentry rule remains correct:

- OpenEverest can be a DBaaS control component after qualification;
- upstream air-gap support must not be claimed;
- LayerSentry may build an offline distribution only as a LayerSentry-engineered profile with deny-all-egress proof;
- OpenEverest v2/developer-preview provider APIs are not the production base until GA/maturity is proven.

---

## 8. Alternative-platform decision record — do not reopen without evidence

The LayerSentry architecture was compared with the following approaches. They remain reference/alternative inputs rather than mandatory runtime dependencies.

### Cozystack

Useful patterns to adopt:

- declarative package catalog;
- OCI-backed packages/artifacts;
- Flux-based reconciliation;
- tenant/self-service platform UX;
- air-gap-oriented release discipline.

Decision:

- do **not** embed the complete Cozystack cloud/platform layer under LayerSentry because CloudStack already owns IaaS and CAPI/RKE2 own the Kubernetes lifecycle;
- reuse the package/lifecycle ideas, not another infrastructure authority.

### Otomi / Akamai App Platform

Useful as a UX/platform-engineering reference for:

- curated application catalog;
- policy-based application enablement;
- developer/self-service experience;
- integrated observability/security/GitOps patterns;
- modern Gateway API direction.

Decision:

- do not make it a mandatory LayerSentry control plane; LayerSentry already owns the customer portal, CloudStack-specific infrastructure workflows and offline enterprise storage integrations.

### KubeBlocks

Useful as a database-operator/abstraction reference.

Current repository license validation shows **AGPL-3.0**.

Decision:

- do not copy/embed KubeBlocks code into a closed/commercial LayerSentry distribution without a deliberate legal/licensing decision and compliance plan;
- architecture concepts may be studied independently of code reuse.

### KubeDB Platform

KubeDB Platform is a credible commercial alternative for a broad white-label DBaaS with many engines and documented offline/air-gap positioning.

Decision:

- OpenEverest + LayerSentry provider/facade remains the open-source-control direction;
- KubeDB must remain an explicit commercial/OEM alternative if time-to-market, database breadth or supported white-label/offline capability becomes more important than open-source ownership;
- do not spend months recreating capabilities if a later business/OEM analysis shows KubeDB is materially lower-risk and commercially acceptable.

### Rancher / Turtles

CAPRKE2 is useful independently. Rancher/Turtles is not required in the initial LayerSentry critical path because it introduces another management product and does not remove CAPC qualification work.

Decision:

- do not add Rancher as a mandatory dependency without a new decision showing measurable operational benefit.

---

## 9. Completion rule for the specialist master-context suite

The architecture is considered documentation-complete only when the following are all present and mutually consistent:

1. `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` — stable module architecture;
2. this addendum — exact integration clarifications that prevent unsafe interpretation;
3. `codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md` — implementation ownership/order;
4. current dated compatibility/evidence record — volatile exact versions/source findings;
5. canonical/global policies for security, release, DR, RBAC and CloudStack-core preservation.

The addendum does not make the module `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`.

The next implementation gate is **E0 compatibility qualification**, with hard stop on:

- CAPC/CAPI/CAPRKE2 contract mismatch that fails actual reconciliation;
- missing RKE2 9345 HA endpoint;
- CAPC deletion of CSI/unowned DATADISK volumes;
- unsafe multiple-node-disk lifecycle;
- CloudStack CSI project/resize non-idempotency;
- any air-gap dependency escape;
- any DBaaS data-integrity failure.

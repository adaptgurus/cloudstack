# LayerSentry Master-Context Validation Completion Audit

**Date:** 2026-09-06  
**Repository:** `adaptgurus/cloudstack`  
**Branch:** `layersentry/4.22.1.1-ui`  
**Validation subject:** LayerSentry Kubernetes/DBaaS/APaaS/Streaming master-context suite and active non-overlap governance  
**Validation result:** `CONDITIONAL_PASS / DESIGN_CORRECTED / GOVERNANCE_COMPLETE`  
**Production certification:** not established  
**Runtime mutation by this validation task:** none

## 1. What was validated

The validation re-read the current specialist Kubernetes master context and checked its material technical assumptions against current upstream source/release evidence, including:

- CAPI release/contract support;
- CAPC release and current source;
- CAPRKE2 current and historical release dependencies;
- RKE2 current release/registration-port behavior;
- CAPC control-plane LoadBalancer implementation;
- CAPC VM/DATADISK deletion behavior;
- CAPC direct DiskOffering model;
- CloudStack CSI current release/project/resize code;
- OpenEverest versioned support boundary;
- CloudStack SharedFS/storage semantics;
- central Flux remote-cluster design;
- package/ISO/QCOW2 lifecycle;
- alternative-platform decisions (Cozystack, Otomi/Akamai App Platform, KubeBlocks, KubeDB, Rancher/Turtles).

The detailed source findings are recorded in:

`docs/layersentry/evidence/k8s/2026-09-06-k8s-master-context-full-validation.md`

Stable integration corrections are recorded in:

`docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md`

## 2. Architecture conclusion

The selected Kubernetes architecture remains:

```text
LayerSentry UI/API
  -> CAPI
      -> CAPC -> CloudStack 4.22.1.1 / KVM
      -> CAPRKE2 -> RKE2
  -> central Flux -> selected packages
  -> CloudStack native APIs outside CAPC Machine ownership
  -> CloudStack CCM for supported L4
  -> Gateway API / OEM controllers for L7/WAF
```

No evidence justified replacing this with native CKS, Rancher, AWX, XaaS or a custom full Kubernetes lifecycle engine.

However, the old context was not safe to call “complete as-is.” The following corrections are now mandatory:

1. exact CAPI/CAPC/CAPRKE2 release tuple qualification;
2. explicit RKE2 `9345` control-plane/join endpoint in addition to Kubernetes API `6443`;
3. CAPC attached-DATADISK ownership fix before stateful Machine deletion/remediation;
4. explicit NodeDiskSet-style lifecycle before arbitrary multiple direct node disks are production-ready;
5. CloudStack CSI `3.0.2` project/resize/idempotency E2E rather than assuming old or new behavior;
6. explicit alternative-platform decision record.

## 3. Exact current candidate lanes

### Released legacy overlap

```text
CAPI    1.9.6
CAPC    0.6.1
CAPRKE2 0.15.0
```

Valid reference lane, but CAPI 1.9 workload support does not meet the LayerSentry Kubernetes 1.36 target.

### First modern qualification candidate

```text
CloudStack 4.22.1.1
CAPI       1.13.5
CAPRKE2    0.25.2
CAPC       0.6.1
RKE2       1.36.4+rke2r1
```

This uses CAPI's temporary compatibility with v1beta1 infrastructure providers. It is a **test candidate**, not a certified tuple.

### Modern-contract candidate

```text
CAPI       1.13.x
CAPRKE2    0.25.2-compatible
CAPC       reviewed/pinned v1beta2-contract build from upstream PR #493 or later released equivalent
RKE2       1.36.x
```

PR #493 was open/unmerged during validation, so this cannot be represented as an upstream stable CAPC release.

## 4. Hard production blockers

The K8s/Data Services implementation must not pass E0 while any of these remains unresolved:

- no HA endpoint for RKE2 TCP `9345`;
- CAPC may delete unowned/CSI-attached DATADISK volumes during Machine deletion;
- multiple direct worker disks lack explicit ownership/retain/delete semantics;
- CloudStack CSI project resize/idempotency unproven on 4.22.1.1;
- offline create/scale/repair/replace/upgrade not proven behind deny-all Internet egress;
- stateful PVC does not survive Machine replacement;
- DB data-integrity/backup/PITR/failover tests fail.

## 5. Concurrent branch changes detected during validation

While this validation was running, the same branch received separate commits that added:

- `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
- additions in `AGENTS.md` defining the VM-native Single-OS path and Workstream F;
- `tools/layersentry/single-os/rocky9-hardening` runtime/source implementation.

These changes were **not created by the Kubernetes validation work**.

They were inspected because they changed active governance while validation was in progress.

The Single-OS architecture explicitly states that it is a separate VM-native lifecycle path and must not be merged with the Kubernetes/CAPI/RKE2 lifecycle. This is compatible with the validated Kubernetes architecture.

A governance gap was found: `AGENTS.md` declared Workstream F but no Workstream-F contract existed in `docs/layersentry/codex/`.

This validation completed the governance by adding:

`docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`

and updated the Codex startup index so E and F remain separate.

The runtime hardening script itself was **not modified by this validation task** and is not promoted to live/production status merely because it exists in source.

## 6. Current non-overlap model

### Workstream E

Owns:

- CAPI/CAPC/CAPRKE2/RKE2;
- Kubernetes package plane/Flux;
- Kubernetes DBaaS/APaaS/Streaming;
- Kubernetes storage/VIP/Gateway/WAF integrations.

### Workstream F

Owns:

- Rocky Linux 9 VM-native guest lifecycle;
- `layersentryd`/provider model;
- Single-OS package/install/upgrade/repair/uninstall;
- one-VM Hyper-V acceptance/hardening evidence.

### Shared only by clean contracts

- CloudStack APIs;
- tenant/project/RBAC;
- common UI design shell;
- secure-engineering/release policy;
- approved secret/audit/evidence primitives.

Never share one lifecycle state machine/controller between E and F.

## 7. Documentation/governance state after validation

Kubernetes module mandatory context suite:

1. `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
2. `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
3. `LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md`;
4. latest dated validation under `evidence/k8s/`;
5. `codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`.

Single-OS module mandatory context suite:

1. `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
2. `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
3. secure-engineering policy;
4. `codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`;
5. exact live evidence when available.

`docs/layersentry/codex/README.md` now routes both paths explicitly.

## 8. Status discipline

The completed documentation is a validated design/governance contract.

It does **not** promote:

- CAPC + CloudStack 4.22.1.1 to production-supported;
- RKE2 1.36.4 to LayerSentry Certified;
- CloudStack CSI auto-grow to certified;
- OpenEverest air-gap to upstream-supported;
- DBaaS/APaaS/Streaming to production-ready;
- Single-OS hardening source to `LIVE_VERIFIED`;
- any hardware ADC/WAF/GPU/RDMA combination to certified.

Those states require implementation and exact CI/live/destructive evidence.

## 9. Next gate

For Kubernetes/Data Services, start Workstream E **E0**, not DBaaS feature coding:

1. install/test the modern candidate tuple;
2. solve 6443 + 9345 endpoint ownership;
3. prove CAPI/CAPC lifecycle;
4. fix CAPC volume ownership;
5. prove PVC survival;
6. qualify one storage path;
7. run complete deny-all-egress lifecycle;
8. compare CAPC v1beta2-contract candidate;
9. then start PostgreSQL DBaaS vertical slice.

For Single-OS, Workstream F proceeds independently under its one-VM acceptance ceiling.
